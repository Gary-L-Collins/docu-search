from pathlib import Path
from pypdf import PdfReader

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
    meta = r.metadata or {}
    raw_author = getattr(meta, "author", None)
    raw_title = getattr(meta, "title", pdf_path)
    author = raw_author or "Author Not Found in Metadata"
    title = raw_title or "Title Not Found in Metadata"

    document = ParsedDocument(document_id, author, title, texts, pdf_path)

    return document


