from pathlib import Path
from typing import Dict, List
from pypdf import PdfReader
from uuid import uuid4

from .schemas import ParsedDocument

def read_pdf(pdf_path: Path | str, document_id: str) -> ParsedDocument:
    """
    for reading in pdf
    :param pdf_lists:
    :return: list of strings
    """
    r = PdfReader(str(pdf_path))
    # getting text
    texts = []
    for page_number, p in enumerate(r.pages):
        t = p.extract_text()
        if t:
            texts.append((page_number, t))

    # getting metadata
    meta = r.metadata
    author = meta.author if meta.author != "" else "Author Not Found in Metadata"
    title = meta.title if meta.title != "" else "Title Not Found in Metadata"

    document = ParsedDocument(document_id, author, title, texts, pdf_path)

    return document



