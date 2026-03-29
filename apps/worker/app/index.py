from pathlib import Path
from typing import List
from .schemas import Chunk

import chromadb
from chromadb import Client

def delete_collection(client: Client, collection: str):
    if any(col.name == collection for col in client.list_collections()):
        client.delete_collection(collection)


def delete_document_embeddings(client: Client, collection: str, document_id: str):
    if not any(col.name == collection for col in client.list_collections()):
        return

    col = client.get_collection(collection)
    col.delete(where={"document_id": document_id})

def upload_embeddings(
        chunks: List[Chunk],
        db_directory: Path,
        collection: str,
        replace: bool=False
):
    """
    This function upserts vector embeddings.
    :param chunks: `Chunk` dataclass object of text data
    :param db_directory: directory for the db
    :param collection: name of the collection in the `db_directory`
    :param replace: If `True`, then the whole vector database is replaced with the embedding database of chunks
                    If `False`, then the vector database is updated with the vector embeddings from chunks
    :return:
    """

    # getting vector embeddings this should be done before running this function
    # embed_chunks(model, chunks)

    # create output folder
    Path(db_directory).mkdir(parents=True, exist_ok=True)

    # preparing client
    client = chromadb.PersistentClient(path=db_directory)

    if replace:
        delete_collection(client, collection)

    col = client.get_or_create_collection(
        name=collection,
        configuration={"hnsw": {"space": "cosine"}}
    )

    # upserting to chroma db
    ids, metadatas, texts, vecs = [], [], [], []
    for c in chunks:
        if c.embedding is None:
            continue

        ids.append(c.id)
        metadatas.append(
            {
                "document_id": c.id.rsplit("_", 1)[0],
                "author": c.author,
                "title": c.title,
                "path": str(c.path),
                "start_page": c.pages[0],
                "end_page": c.pages[1],
                "size": c.size,
            }
        )
        texts.append(c.text)
        vecs.append(c.embedding)

    start, n = 0, len(ids)
    while start < n:
        end = min(start+2048, n)
        col.upsert(
            ids=ids[start: end],
            embeddings=vecs[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end]
        )
        start = end

