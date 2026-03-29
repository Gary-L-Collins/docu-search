import chromadb

from .chunk import process_pdf_texts
from .embed import embed_chunks, get_embed_model
from .index import delete_document_embeddings, upload_embeddings
from .ingest import read_pdf
from .schemas import EmbedJob, JobStatus, JobType


def _require_pdf_path(job: EmbedJob) -> str:
    if not job.pdf_path:
        raise ValueError("Upload job requires `pdf_path`.")
    return job.pdf_path


def upload_job(job: EmbedJob) -> JobStatus:
    job.job_status = JobStatus.RUNNING
    job.error_message = None

    try:
        pdf_path = _require_pdf_path(job)
        document = read_pdf(pdf_path, job.document_id)
        chunks = process_pdf_texts([document], chunk_size=job.chunk_size, overlap=job.overlap)
        if not chunks:
            raise ValueError("No text chunks were generated from the PDF.")

        embed_model = get_embed_model(job.embed_model)
        embed_chunks(
            embed_model,
            chunks,
            process_size=job.embed_process_size,
            batch_size=job.embed_batch_size,
        )

        if job.replace:
            client = chromadb.PersistentClient(path=job.db_directory)
            delete_document_embeddings(client, job.collection, job.document_id)

        upload_embeddings(chunks, job.db_directory, job.collection, replace=False)
        job.job_status = JobStatus.SUCCESS
    except Exception as exc:
        job.job_status = JobStatus.FAILURE
        job.error_message = str(exc)

    return job.job_status


def delete_job(job: EmbedJob) -> JobStatus:
    job.job_status = JobStatus.RUNNING
    job.error_message = None

    try:
        client = chromadb.PersistentClient(path=job.db_directory)
        delete_document_embeddings(client, job.collection, job.document_id)
        job.job_status = JobStatus.SUCCESS
    except Exception as exc:
        job.job_status = JobStatus.FAILURE
        job.error_message = str(exc)

    return job.job_status


def process_job(job: EmbedJob) -> JobStatus:
    if job.job_type == JobType.UPLOAD:
        return upload_job(job)
    if job.job_type == JobType.DELETE:
        return delete_job(job)

    raise ValueError(f"Unsupported job type: {job.job_type}")
