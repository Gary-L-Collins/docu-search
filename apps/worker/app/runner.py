from datetime import datetime, timezone

import chromadb
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .chunk import process_pdf_texts
from .embed import embed_chunks, get_embed_model
from .index import delete_document_embeddings, upload_embeddings
from .ingest import read_pdf
from .schemas import PreparedChunk
from ...shared.schemas import JobStatus, JobType
from ...shared.models import DocumentChunks, Documents, IngestionJobs


def _require_pdf_path(job: IngestionJobs) -> str:
    if not job.pdf_path:
        raise ValueError("Upload job requires `pdf_path`.")
    return job.pdf_path

def _prepare_chunks(job: IngestionJobs):
    pdf_path = _require_pdf_path(job)
    parsed_document = read_pdf(pdf_path, str(job.document_id))

    worker_chunks = process_pdf_texts(
        [parsed_document],
        chunk_size=job.chunk_size,
        overlap=job.overlap,
    )
    if not worker_chunks:
        raise ValueError("No text chunks were generated from the PDF.")

    model = get_embed_model(job.embed_model)
    embed_chunks(
        model,
        worker_chunks,
        process_size=job.embed_process_size,
        batch_size=job.embed_batch_size,
    )

    sql_chunks = []
    for idx, chunk in enumerate(worker_chunks):
        sql_chunks.append(
            PreparedChunk(
                chunk_index=idx,
                vector_id=chunk.id,
                chunk_text=chunk.text,
                start_page=chunk.pages[0],
                end_page=chunk.pages[1],
                char_count=len(chunk.text),
            )
        )

    return parsed_document, worker_chunks, sql_chunks

def _replace_document_chunks(session: Session, document_id: int, sql_chunks: list[PreparedChunk]) -> None:
    session.execute(
        delete(DocumentChunks).where(DocumentChunks.document_id == document_id)
    )

    session.add_all(
        [
            DocumentChunks(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                char_count=chunk.char_count,
                vector_id=chunk.vector_id,
            )
            for chunk in sql_chunks
        ]
    )

def upload_job(session: Session, job: IngestionJobs) -> JobStatus:
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    job.error_message = None
    job.finished_at = None
    session.flush()

    try:
        parsed_document, worker_chunks, sql_chunks = _prepare_chunks(job)
        document = session.get(Documents, job.document_id)
        if document is None:
            raise ValueError(f"Document {job.document_id} not found.")

        document.title = parsed_document.title
        document.author = parsed_document.author
        document.page_count = len(parsed_document.texts)

        if job.replace_existing:
            client = chromadb.PersistentClient(path=job.db_directory)
            delete_document_embeddings(client, job.corpus.chroma_collection, str(job.document_id))

        _replace_document_chunks(session, job.document_id, sql_chunks)
        upload_embeddings(worker_chunks, job.db_directory, job.corpus.chroma_collection, replace=False)

        job.status = JobStatus.SUCCESS
        job.leased_until = None
        job.finished_at = datetime.now(timezone.utc)
        session.commit()
    except Exception as exc:
        session.rollback()
        refreshed_job = session.get(IngestionJobs, job.id)
        if refreshed_job is None:
            raise
        refreshed_job.status = JobStatus.FAILURE
        refreshed_job.leased_until = None
        refreshed_job.error_message = str(exc)
        refreshed_job.finished_at = datetime.now(timezone.utc)
        session.commit()

    return job.status


def delete_job(session: Session, job: IngestionJobs) -> JobStatus:
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    job.error_message = None
    job.finished_at = None
    session.flush()

    try:
        client = chromadb.PersistentClient(path=job.db_directory)
        delete_document_embeddings(client, job.corpus.chroma_collection, str(job.document_id))
        session.execute(
            delete(DocumentChunks).where(DocumentChunks.document_id == job.document_id)
        )
        job.status = JobStatus.SUCCESS
        job.finished_at = datetime.now(timezone.utc)
        job.leased_until = None
        session.commit()
    except Exception as exc:
        session.rollback()
        refreshed_job = session.get(IngestionJobs, job.id)
        if refreshed_job is None:
            raise
        refreshed_job.status = JobStatus.FAILURE
        refreshed_job.error_message = str(exc)
        refreshed_job.finished_at = datetime.now(timezone.utc)
        refreshed_job.leased_until = None
        session.commit()

    return job.status


def process_job(session: Session, job: IngestionJobs) -> JobStatus:
    if job.job_type == JobType.UPLOAD:
        return upload_job(session, job)
    if job.job_type == JobType.DELETE:
        return delete_job(session, job)

    raise ValueError(f"Unsupported job type: {job.job_type}")
