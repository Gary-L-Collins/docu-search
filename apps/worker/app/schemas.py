from dataclasses import dataclass
from typing import List, Tuple
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


@dataclass
class PreparedChunk:
    chunk_index: int
    vector_id: str
    chunk_text: str
    start_page: int
    end_page: int
    char_count: int