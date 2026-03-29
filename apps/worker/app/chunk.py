from typing import List, Tuple
from bisect import bisect_right
from .schemas import Chunk, ParsedDocument


def _page_for_offset(prefix_char: list[int], char_count: list[tuple[int, int]], offset: int) -> int:
    # Map a character offset to the page containing that character.
    page_idx = bisect_right(prefix_char, offset) - 1
    page_idx = max(0, min(page_idx, len(char_count) - 1))
    return char_count[page_idx][1]

def chunkify_text(text: str, char_count: Tuple[int, int], chunk_size: int=1024, overlap: int=256) -> List[Tuple[int, int, str]]:
    """
    This function chunks up a string of text using a sliding window
    :param text: the text
    :param char_count: List of length of each page
    :param chunk_size: the size of the window
    :param overlap: the size of the overlapping portions of each chunk
    :return: a list of chunks
    """

    if not text:
        return []

    assert overlap < chunk_size, "Overlap must be smaller than chunk_size"

    # prefix sum for determining what pages you are on
    prefix_char = [0] * (len(char_count)+1)
    for i, (c, p) in enumerate(char_count):
        prefix_char[i+1] = prefix_char[i] + c

    # variables for tracking chunks
    out, start, text_size = [], 0, len(text)

    while start < text_size:
        end = min(start + chunk_size, text_size)
        t = text[start:end].strip()

        # get pages
        start_page = _page_for_offset(prefix_char, char_count, start)
        end_page = _page_for_offset(prefix_char, char_count, max(start, end - 1))

        if t:
            out.append((start_page, end_page, t))

        if end == text_size:
            break

        start = end - overlap

    return out

def process_pdf_texts(documents: List[ParsedDocument], chunk_size=1024, overlap=256) -> List[Chunk]:
    """
    For processing parsed pdfs from `collect_pdfs`
    :param documents: List object from `collect_pdfs`
    :return: List of Chunks
    """
    out = []
    for v in documents:
        title = v.title
        author = v.author
        id = v.id
        path = v.path
        texts = v.texts
        text_flatten = "".join([t[1] for t in texts])
        char_count = [(len(t[1]), t[0]) for t in texts]

        # getting chunked text
        chunked_texts = chunkify_text(text_flatten, char_count, chunk_size, overlap)
        for i, ct in enumerate(chunked_texts):
            start_page, end_page, text = ct
            chunk = Chunk(id + f"_{i:d}", author, title, [start_page, end_page], path, chunk_size, text, None)
            out.append(chunk)

    return out


