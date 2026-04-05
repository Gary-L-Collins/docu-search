import numpy as np
from typing import List
from .schemas import Chunk
from sentence_transformers import SentenceTransformer

DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def get_embed_model(model_name: str) -> SentenceTransformer:
    if model_name == "mini":
        resolved_name = "sentence-transformers/all-MiniLM-L6-v2"
    elif model_name == "mpnet":
        resolved_name = "sentence-transformers/all-mpnet-base-v2"
    elif model_name == "instructor":
        resolved_name = "hkunlp/instructor-base"
    else:
        resolved_name = model_name or DEFAULT_EMBED_MODEL

    return SentenceTransformer(resolved_name)

def embed_text(model: SentenceTransformer, text: str|List[str], batch_size: int=64) -> np.ndarray | None:
    if not text:
        return None

    texts = [text] if isinstance(text, str) else text
    vecs = model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
    return vecs


def embed_chunks(model: SentenceTransformer, chunks: List[Chunk], process_size: int=1024, batch_size: int=64):
    """
    This function takes the list of `Chunks` (created by `.chunk.chunkify_text`) and creates an embedding
    :param model: Embedding model
    :param chunks: List of `Chunk` data objects
    :param process_size: size of text list to give to `embed_text`
    :param batch_size: batch size for `embed_text`
    :return:
    """
    start, n = 0, len(chunks)
    while start < n:
        end = min(n, start + process_size)
        c = chunks[start:end]
        t = [cc.text for cc in c]
        vecs = embed_text(model, t, batch_size)
        for i, vec in enumerate(vecs):
            chunks[start + i].embedding = vec
        start = end


