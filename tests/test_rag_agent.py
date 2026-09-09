"""RAG agent tests. A stub LLM stands in for Groq, so these run offline."""

import pytest

from agents.rag_agent import NO_EVIDENCE, answer_question, build_context


class StubLLM:
    """Records the prompt it was given and returns a canned reply."""

    def __init__(self, reply="Semaglutide reduced weight [1]."):
        self.reply = reply
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages)
        return type("Reply", (), {"content": self.reply})()


class StubRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.queries = []

    def search(self, query, k=10, filters=None):
        self.queries.append((query, k, filters))
        return self.chunks


def _chunk(doc_id, text, source="pubmed", title="A title"):
    return {
        "chunk_id": f"{source}:{doc_id}:0",
        "text": text,
        "metadata": {
            "source": source, "document_id": doc_id, "title": title,
            "url": f"https://example.test/{doc_id}", "date": "2026-01-01",
        },
    }


CHUNKS = [
    _chunk("1", "Semaglutide reduced body weight.", title="Weight study"),
    _chunk("2", "Tirzepatide improved outcomes.", "clinicaltrials", "Trial two"),
]


def test_build_context_numbers_each_source():
    context, citations = build_context(CHUNKS)
    assert "[1]" in context and "[2]" in context
    assert len(citations) == 2


def test_build_context_gives_one_number_per_document_not_per_chunk():
    chunks = CHUNKS + [_chunk("1", "More from the same study.", title="Weight study")]
    context, citations = build_context(chunks)
    assert len(citations) == 2
    assert [c["number"] for c in citations] == [1, 2]


def test_citations_carry_what_the_reader_needs():
    _, citations = build_context(CHUNKS)
    first = citations[0]
    assert first["document_id"] == "1"
    assert first["source"] == "pubmed"
    assert first["title"] == "Weight study"
    assert first["url"] == "https://example.test/1"


def test_context_includes_the_chunk_text():
    context, _ = build_context(CHUNKS)
    assert "Semaglutide reduced body weight." in context


def test_answer_question_returns_answer_citations_and_documents():
    result = answer_question("what helps weight loss?", StubRetriever(CHUNKS), StubLLM())
    assert result["answer"] == "Semaglutide reduced weight [1]."
    # The stub cited [1] only, so [2] is dropped. Every retrieved chunk is
    # still returned so the UI can show what was searched.
    assert [c["number"] for c in result["citations"]] == [1]
    assert result["documents"] == CHUNKS


def test_the_question_and_the_context_both_reach_the_model():
    llm = StubLLM()
    answer_question("what helps weight loss?", StubRetriever(CHUNKS), llm)
    prompt = str(llm.prompts[0])
    assert "what helps weight loss?" in prompt
    assert "Semaglutide reduced body weight." in prompt


def test_no_retrieved_chunks_means_no_model_call():
    llm = StubLLM()
    result = answer_question("anything", StubRetriever([]), llm)
    assert result["answer"] == NO_EVIDENCE
    assert result["citations"] == []
    assert llm.prompts == []


def test_filters_are_passed_through_to_the_retriever():
    retriever = StubRetriever(CHUNKS)
    answer_question("q", retriever, StubLLM(), k=4, filters={"source": "pubmed"})
    assert retriever.queries[0] == ("q", 4, {"source": "pubmed"})


def test_unused_citations_are_dropped_from_the_answer():
    # The model cited only [1], so [2] should not appear in the source list.
    result = answer_question("q", StubRetriever(CHUNKS), StubLLM("Only this one [1]."))
    assert [c["number"] for c in result["citations"]] == [1]


def test_a_model_that_cites_nothing_keeps_every_source():
    result = answer_question("q", StubRetriever(CHUNKS), StubLLM("No citations here."))
    assert len(result["citations"]) == 2


@pytest.mark.llm
def test_live_groq_call_produces_a_grounded_answer():
    from agents.llm import get_llm
    result = answer_question("what helps weight loss?", StubRetriever(CHUNKS), get_llm())
    assert result["answer"]
    assert "[1]" in result["answer"] or "[2]" in result["answer"]
