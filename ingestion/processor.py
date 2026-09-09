"""Clean documents and split them into retrievable chunks.

Retrieval works better on chunks than whole documents: a study's results
section can be returned without dragging along its eligibility criteria.
"""

import re

MAX_CHARS = 800
OVERLAP = 100

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SPACES = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def clean_text(text: str) -> str:
    """Strip control characters and collapse whitespace, keeping paragraphs."""
    text = _CONTROL.sub("", text)
    text = _SPACES.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def _split_units(text: str, max_chars: int) -> list[str]:
    """Break text into pieces no longer than max_chars.

    Paragraphs first, then sentences, then a hard cut for anything still
    oversized (long tables and unpunctuated blocks turn up in both sources).
    """
    units: list[str] = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue
        for sentence in _SENTENCE_END.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= max_chars:
                units.append(sentence)
            else:
                units.extend(
                    sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars)
                )
    return units


def _tail(text: str, overlap: int) -> str:
    """Return roughly the last `overlap` characters, snapped to a word boundary."""
    if overlap <= 0 or len(text) <= overlap:
        return text
    piece = text[-overlap:]
    space = piece.find(" ")
    return piece[space + 1:] if space != -1 else piece


def chunk_document(
    document: dict, max_chars: int = MAX_CHARS, overlap: int = OVERLAP
) -> list[dict]:
    """Split one document into overlapping chunks carrying its metadata."""
    title = document.get("title", "")
    body = clean_text(document.get("text", ""))
    if not body:
        return []
    # Prefix the title so a chunk still identifies itself out of context.
    if title and not body.startswith(title):
        body = f"{title}\n\n{body}"

    units = _split_units(body, max_chars)
    texts: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if current and len(candidate) > max_chars:
            texts.append(current)
            carry = _tail(current, overlap)
            current = f"{carry}\n\n{unit}" if carry else unit
        else:
            current = candidate
    if current:
        texts.append(current)

    source = document.get("source", "")
    document_id = document.get("document_id", "")
    chunks = []
    for index, text in enumerate(texts):
        metadata = dict(document.get("metadata", {}))
        metadata["chunk_index"] = index
        chunks.append({
            "chunk_id": f"{source}:{document_id}:{index}",
            "text": text,
            "metadata": metadata,
        })
    return chunks


def process_documents(
    documents: list[dict], max_chars: int = MAX_CHARS, overlap: int = OVERLAP
) -> list[dict]:
    """Chunk every document into one flat list."""
    chunks: list[dict] = []
    for document in documents:
        chunks.extend(chunk_document(document, max_chars, overlap))
    return chunks
