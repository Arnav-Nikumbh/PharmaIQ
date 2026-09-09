"""Routing, context extraction and synthesis. Stub LLM, real database."""

import pytest

from agents.parsing import parse_json_object
from agents.supervisor import ROUTES, classify
from agents.synthesis_agent import synthesize
from agents.context_extractor import extract_context
from database.db_manager import DBManager, build_database


class StubLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages)
        reply = self.replies.pop(0) if self.replies else ""
        return type("Reply", (), {"content": reply})()


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("ctx") / "test.db"
    build_database(path)
    return DBManager(path)


# --- tolerant JSON parsing -------------------------------------------------

def test_parse_json_object_reads_plain_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_ignores_surrounding_prose():
    assert parse_json_object('Sure! {"a": 1} hope that helps') == {"a": 1}


def test_parse_json_object_reads_a_fenced_block():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_object_returns_none_when_there_is_no_object():
    assert parse_json_object("no json at all") is None


# --- supervisor ------------------------------------------------------------

def test_classify_returns_the_route_the_model_chose():
    assert classify("what does research say?", StubLLM('{"route": "research"}')) == "research"


def test_classify_accepts_every_known_route():
    for route in ROUTES:
        assert classify("q", StubLLM('{"route": "%s"}' % route)) == route


def test_an_unknown_route_falls_back_to_cross():
    assert classify("q", StubLLM('{"route": "banana"}')) == "cross"


def test_unparseable_output_falls_back_to_cross():
    assert classify("q", StubLLM("I think this is a data question")) == "cross"


# --- context extraction ----------------------------------------------------

CHUNKS = [{
    "chunk_id": "pubmed:1:0",
    "text": "Weight loss therapies showed positive outcomes in obesity.",
    "metadata": {"source": "pubmed", "document_id": "1", "title": "T"},
}]

EXTRACTED = """{
  "entities": {"therapy": ["semaglutide"], "condition": ["obesity"],
               "product_class": ["Weight Management"], "regions": []},
  "insights": ["positive weight loss outcomes"]
}"""


def test_extracted_entities_are_returned(db):
    context = extract_context(CHUNKS, StubLLM(EXTRACTED), db)
    assert context["entities"]["condition"] == ["obesity"]
    assert context["insights"] == ["positive weight loss outcomes"]


def test_a_therapy_area_present_in_the_database_is_matched(db):
    context = extract_context(CHUNKS, StubLLM(EXTRACTED), db)
    assert "Weight Management" in context["matched"]["categories"]


def test_an_invented_therapy_area_is_not_matched(db):
    reply = '{"entities": {"product_class": ["Teleportation Therapy"]}, "insights": []}'
    context = extract_context(CHUNKS, StubLLM(reply), db)
    assert context["matched"]["categories"] == []
    assert "Teleportation Therapy" in context["unmatched"]


def test_matching_ignores_case(db):
    reply = '{"entities": {"product_class": ["weight management"]}, "insights": []}'
    context = extract_context(CHUNKS, StubLLM(reply), db)
    assert context["matched"]["categories"] == ["Weight Management"]


def test_no_chunks_means_an_empty_context_and_no_model_call(db):
    llm = StubLLM(EXTRACTED)
    context = extract_context([], llm, db)
    assert context["entities"] == {}
    assert llm.prompts == []


def test_unparseable_extraction_returns_an_empty_context(db):
    context = extract_context(CHUNKS, StubLLM("sorry, no idea"), db)
    assert context["entities"] == {}
    assert context["matched"]["categories"] == []


# --- synthesis -------------------------------------------------------------

RAG = {"answer": "Research says weight therapies work [1].",
       "citations": [{"number": 1, "source": "pubmed", "document_id": "1",
                      "title": "A study", "url": "https://example.test/1"}]}
SQL = {"sql": "SELECT 1", "results": [{"Region": "North", "Sales": 100}], "error": None}


def test_synthesis_passes_both_sources_to_the_model():
    llm = StubLLM("Final answer")
    synthesize("q", RAG, SQL, llm)
    prompt = str(llm.prompts[0])
    assert "Research says weight therapies work" in prompt
    assert "North" in prompt


def test_synthesis_appends_the_source_list():
    result = synthesize("q", RAG, SQL, StubLLM("Final answer"))
    assert "Final answer" in result
    assert "https://example.test/1" in result


def test_synthesis_without_citations_adds_no_source_list():
    result = synthesize("q", {"answer": "x", "citations": []}, SQL, StubLLM("Final answer"))
    assert "Sources" not in result


def test_synthesis_reports_a_failed_query_honestly():
    failed = {"sql": "SELECT bad", "results": [], "error": "no such column: bad"}
    llm = StubLLM("Final answer")
    synthesize("q", RAG, failed, llm)
    assert "no such column" in str(llm.prompts[0])


def test_synthesis_strips_em_dashes_from_the_final_answer():
    result = synthesize("q", RAG, SQL, StubLLM("North — the leader"))
    assert "—" not in result


def test_synthesis_forbids_unsupported_claims():
    llm = StubLLM("Final answer")
    synthesize("q", RAG, SQL, llm)
    rules = llm.prompts[0][0]["content"]
    assert "Every statement must be supported by the research or the data" in rules
    assert "not for speculation" in rules
