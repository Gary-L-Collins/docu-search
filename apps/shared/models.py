"""
Relational data model for the document research system.

How the main entities interact:

1. A user owns one or more corpora.
   Corpora are the top-level collections a researcher queries against.

2. A user uploads a document into a corpus.
   The system creates a document record, links it to the corpus, and enqueues
   an ingestion job.

3. The worker processes the ingestion job.
   It reads the source PDF, extracts metadata and page text, chunks the text,
   computes embeddings, and updates job status as it runs.

4. Each generated chunk is stored in SQL as document metadata plus a stable
   vector identifier.
   The actual embedding vector is stored in Chroma, while SQL remains the
   source of truth for ownership, metadata, lifecycle, and query history.

5. When a researcher submits a query, the API records the query, searches the
   corpus's Chroma collection, maps returned vector IDs back to chunk records,
   stores ranked query results, and saves the final generated answer.

In short:
SQL stores users, corpora, documents, chunks, jobs, and query history.
Chroma stores embeddings for chunk retrieval.
"""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (String, Integer, ForeignKey, DateTime, Boolean,
                        Enum as SQLEnum, Text, Float, UniqueConstraint, Index)
from sqlalchemy.sql import func

from .schemas import JobType, JobStatus, QueryStatus, SessionStatus
from datetime import datetime, timedelta, timezone

SESSION_TIMEOUT_MINUTES = 120

def default_timeout() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)

class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    documents: Mapped[list["Documents"]] = relationship(back_populates="owner")
    ingestion_jobs: Mapped[list["IngestionJobs"]] = relationship(back_populates="user")



class UserSessions(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_status: Mapped[SessionStatus] = mapped_column(SQLEnum(SessionStatus), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=default_timeout,
        nullable=False,
    )

class Corpora(Base):
    """
    table of corpora
    """
    __tablename__ = "corpora"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_corpus_owner_name"),
        UniqueConstraint("chroma_collection", name="uq_corpus_chroma_collection"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    chroma_collection: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    documents: Mapped[list["Documents"]] = relationship(
        secondary="corpus_documents",
        back_populates="corpora",
    )
    ingestion_jobs: Mapped[list["IngestionJobs"]] = relationship(back_populates="corpus")


class Documents(Base):
    """
        Table of documents
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_path: Mapped[str] = mapped_column(String(255), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    corpora: Mapped[list["Corpora"]] = relationship(
        secondary="corpus_documents",
        back_populates="documents",
    )
    owner: Mapped["Users"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunks"]] = relationship(back_populates="document")
    ingestion_jobs: Mapped[list["IngestionJobs"]] = relationship(back_populates="document")

class DocumentChunks(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
        UniqueConstraint("vector_id", name="uq_chunk_vector_id"),
        Index("ix_chunks_document_id", "document_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    document: Mapped["Documents"] = relationship(back_populates="chunks")

class CorpusDocuments(Base):
    """
        Join table of documents and corpora
    """
    __tablename__ = "corpus_documents"
    corpus_id: Mapped[int] = mapped_column(ForeignKey("corpora.id"), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class IngestionJobs(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    requested_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("user_sessions.id"), nullable=True)
    corpus_id: Mapped[int] = mapped_column(ForeignKey("corpora.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    job_type: Mapped[JobType] = mapped_column(SQLEnum(JobType), nullable=False)
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), nullable=False)
    pdf_path: Mapped[str] = mapped_column(String(255), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    overlap: Mapped[int] = mapped_column(Integer, nullable=False)
    embed_model: Mapped[str | None] = mapped_column(String(255), nullable=False)
    embed_process_size: Mapped[int] = mapped_column(Integer, nullable=False)
    embed_batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    replace_existing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    db_directory: Mapped[str] = mapped_column(String(255), nullable=False)
    error_message: Mapped[str] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )
    leased_until:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    document: Mapped["Documents"] = relationship(back_populates="ingestion_jobs")
    corpus: Mapped["Corpora"] = relationship(back_populates="ingestion_jobs")
    user: Mapped["Users"] = relationship(back_populates="ingestion_jobs")

class Queries(Base):
    """
    Table of user-queries
    """
    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    corpus_id:  Mapped[int] = mapped_column(ForeignKey("corpora.id"), nullable=False)
    # user provided query
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    # gpt answer
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # measurment of confidence
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[QueryStatus] = mapped_column(SQLEnum(QueryStatus), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            nullable=True,
    )
    results: Mapped[list["QueryResults"]] = relationship(back_populates="query")



class QueryResults(Base):
    __tablename__ = "query_results"
    __table_args__ = (
        UniqueConstraint("query_id", "rank", name="uq_query_result_rank"),
        UniqueConstraint("query_id", "chunk_id", name="uq_query_result_chunk"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("queries.id"), nullable=False)
    chunk_id: Mapped[int] = mapped_column(ForeignKey('chunks.id'), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
    )
    query: Mapped["Queries"] = relationship(back_populates="results")
