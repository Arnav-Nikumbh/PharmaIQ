from ingestion.processor import chunk_document, clean_text, process_documents

MAX = 800
OVERLAP = 100


def _document(text, doc_id="NCT1", source="clinicaltrials"):
    return {
        "source": source,
        "document_id": doc_id,
        "title": "A study title",
        "text": text,
        "metadata": {"source": source, "document_id": doc_id, "condition": "Obesity"},
    }


def test_clean_text_collapses_runs_of_whitespace():
    assert clean_text("a   b\t\tc") == "a b c"


def test_clean_text_keeps_paragraph_breaks():
    assert clean_text("one\n\n\n\ntwo") == "one\n\ntwo"


def test_clean_text_removes_control_characters():
    assert clean_text("clean\x00text\x07here") == "cleantexthere"


def test_a_short_document_makes_one_chunk():
    chunks = chunk_document(_document("Short body."))
    assert len(chunks) == 1
    assert chunks[0]["text"] == "A study title\n\nShort body."


def test_chunk_ids_are_stable_and_unique():
    document = _document("word " * 900)
    first = [c["chunk_id"] for c in chunk_document(document)]
    second = [c["chunk_id"] for c in chunk_document(document)]
    assert first == second
    assert len(set(first)) == len(first)
    assert first[0] == "clinicaltrials:NCT1:0"


def test_long_documents_split_into_several_chunks():
    chunks = chunk_document(_document("word " * 900))
    assert len(chunks) > 1


def test_no_chunk_greatly_exceeds_the_size_limit():
    chunks = chunk_document(_document("word " * 2000), max_chars=MAX)
    assert all(len(c["text"]) <= MAX + OVERLAP for c in chunks)


def test_consecutive_chunks_overlap():
    chunks = chunk_document(_document("word " * 900), max_chars=MAX, overlap=OVERLAP)
    tail = chunks[0]["text"][-40:]
    assert tail in chunks[1]["text"]


def test_a_paragraph_longer_than_the_limit_is_still_split():
    chunks = chunk_document(_document("x" * 5000), max_chars=MAX)
    assert len(chunks) > 1
    assert all(c["text"] for c in chunks)


def test_every_chunk_carries_the_document_metadata_and_its_index():
    chunks = chunk_document(_document("word " * 900))
    for index, chunk in enumerate(chunks):
        assert chunk["metadata"]["condition"] == "Obesity"
        assert chunk["metadata"]["document_id"] == "NCT1"
        assert chunk["metadata"]["chunk_index"] == index


def test_chunk_metadata_values_are_all_scalars():
    for chunk in chunk_document(_document("word " * 900)):
        for key, value in chunk["metadata"].items():
            assert isinstance(value, (str, int, float, bool)), f"{key} is {type(value)}"


def test_process_documents_flattens_every_document():
    documents = [_document("word " * 900, "NCT1"), _document("Short.", "NCT2")]
    chunks = process_documents(documents)
    assert {c["metadata"]["document_id"] for c in chunks} == {"NCT1", "NCT2"}
    assert len(chunks) == len(chunk_document(documents[0])) + 1


def test_documents_with_no_text_are_skipped():
    assert process_documents([_document("   ")]) == []
