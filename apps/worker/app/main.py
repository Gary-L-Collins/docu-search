from time import sleep

from .schemas import EmbedJob, JobStatus, JobType
from .worker import process_job

POLL_INTERVAL_SECONDS = 5


def get_next_job() -> EmbedJob | None:
    """
    Job queue
    placeholder
    """

    return None


def persist_job_status(job: EmbedJob) -> None:
    """
    Placeholder for saving the mutated job back to your job store.
    """
    pass


def run_worker() -> None:
    while True:
        job = get_next_job()
        if job is None:
            sleep(POLL_INTERVAL_SECONDS)
            continue

        process_job(job)
        persist_job_status(job)


def main() -> None:
    run_worker()


if __name__ == "__main__":
    main()