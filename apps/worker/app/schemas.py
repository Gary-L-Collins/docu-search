from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum
import numpy as np

@dataclass
class Chunk:
    id: str
    author: str
    title: str
    pages: Tuple[int, int]
    path: str
    size: int
    text: str
    embedding: np.ndarray | None


@dataclass
class ParsedDocument:
    id: str
    author: str
    title: str
    texts: List[Tuple[int, str]]
    path: str

class JobType(str, Enum):
    UPLOAD = "upload"
    DELETE = "delete"

class JobStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"

@dataclass
class EmbedJob:
    job_id: int
    job_type: JobType
    job_status: JobStatus
    document_id: str
    chunk_size: int
    overlap: int
    embed_model: str
    embed_process_size: int
    embed_batch_size: int
    db_directory: str
    collection: str
    replace: bool
    pdf_path: str | None = None
    error_message: str | None = None
