from time import sleep
from datetime import datetime, timezone, timedelta
import os
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, select, or_, and_
from sqlalchemy.orm import Session, joinedload

from ...shared.models import IngestionJobs
from ...shared.schemas import JobStatus
from .runner import process_job

POLL_INTERVAL_SECONDS = 5
JOB_LIMIT_MIN = 10

def get_engine():
    db_host = os.environ["DB_HOST"]
    db_port = os.environ["DB_PORT"]
    db_name = os.environ["DB_NAME"]
    db_user = os.environ["DB_USER"]
    db_password = os.environ["DB_PASSWORD"]
    database_url = f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return create_engine(database_url)


def claim_next_job(session: Session)-> IngestionJobs | None:
    now = datetime.now(timezone.utc)
    stmt = (
        select(IngestionJobs)
        .options(joinedload(IngestionJobs.corpus))
        .where(
            or_(
                IngestionJobs.status == JobStatus.QUEUED,
                and_(
                IngestionJobs.status == JobStatus.RUNNING,
                IngestionJobs.leased_until < now,
                )
            )
        )
        .order_by(IngestionJobs.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    job = session.scalar(stmt)
    if job is None:
        return None

    job.status = JobStatus.RUNNING
    job.leased_until = now + timedelta(minutes=JOB_LIMIT_MIN)
    session.commit()
    session.refresh(job)
    return job


def process_job_by_id(engine, job_id: int):
    with Session(engine) as session:
        job = session.get(IngestionJobs, job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found.")
        return process_job(session, job)


def refresh_lease(engine, job_id: int) -> bool:
    with Session(engine) as session:
        job = session.get(IngestionJobs, job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return False

        job.leased_until = datetime.now(timezone.utc) + timedelta(minutes=JOB_LIMIT_MIN)
        session.commit()
        return True


def run_worker() -> None:
    engine = get_engine()

    with ThreadPoolExecutor(max_workers=1) as pool:
        while True:
            with Session(engine) as session:
                job = claim_next_job(session)

            if job is None:
                sleep(POLL_INTERVAL_SECONDS)
                continue

            future = pool.submit(process_job_by_id, engine, job.id)
            while not future.done():
                sleep(JOB_LIMIT_MIN * 30)
                if not refresh_lease(engine, job.id):
                    break

            future.result()


def main() -> None:
    run_worker()


if __name__ == "__main__":
    main()
