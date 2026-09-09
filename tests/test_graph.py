"""Graph routing tests. Every dependency is stubbed, so no network is used."""

import pytest

from agents.supervisor import OFF_TOPIC_REPLY
from database.db_manager import DBManager, build_database
from graph import ask, build_graph


class RoutingLLM:
    """Answers each stage by looking at the system prompt it was handed."""

    def __init__(self, route):
        self.route = route
        self.seen = []

    def invoke(self, messages):
        system = messages[0]["content"]
        self.seen.append(system.split("\n", 1)[0])
        if "Decide what a user's question needs" in system:
            content = '{"route": "%s"}' % self.route
        elif "pull out the business entities" in system:
            content = ('{"entities": {"product_class": ["Weight Management"]}, '
                       '"insights": ["works"]}')
        elif "You write SQLite queries" in system:
            content = "SELECT CategoryName FROM Categories LIMIT 2"
        elif "You write short business answers" in system:
            content = "The combined answer."
        else:
            content = "Research says it works [1]."
        return type("Reply", (), {"content": content})()


class StubRetriever:
    def search(self, query, k=10, filters=None):
        return [{
            "chunk_id": "pubmed:1:0",
            "text": "Weight loss therapies showed positive outcomes.",
            "metadata": {"source": "pubmed", "document_id": "1", "title": "A study",
                         "url": "https://example.test/1"},
        }]


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("graph") / "test.db"
    build_database(path)
    return DBManager(path)


def _run(route, db, question="a question"):
    llm = RoutingLLM(route)
    state = ask(build_graph(StubRetriever(), db, llm), question, thread_id=route)
    return state, llm


def test_an_off_topic_question_is_turned_away_without_any_work(db):
    state, llm = _run("off_topic", db)
    assert state["answer"] == OFF_TOPIC_REPLY
    assert state.get("sql_query") is None
    assert len(llm.seen) == 1  # only the supervisor was called


def test_a_research_question_retrieves_but_never_queries_the_database(db):
    state, _ = _run("research", db)
    assert state["documents"]
    assert state.get("sql_query") is None
    assert state["answer"].startswith("The combined answer.")


def test_a_data_question_queries_the_database_but_does_not_retrieve(db):
    state, _ = _run("sql", db)
    assert state.get("documents") is None
    assert state["sql_results"][0]["CategoryName"] == "Weight Management"


def test_a_cross_question_retrieves_then_extracts_then_queries(db):
    state, _ = _run("cross", db)
    assert state["documents"]
    assert state["research_context"]["matched"]["categories"] == ["Weight Management"]
    assert state["sql_results"]
    assert state["sql_error"] is None


def test_the_cross_path_runs_its_stages_in_order(db):
    _, llm = _run("cross", db)
    stages = [s for s in llm.seen]
    assert len(stages) == 5  # supervisor, rag, context, sql, synthesis
    assert "Decide what a user's question needs" in stages[0]
    assert "You write short business answers" in stages[-1]


def test_research_citations_reach_the_final_answer(db):
    state, _ = _run("research", db)
    assert "https://example.test/1" in state["answer"]


def test_the_same_thread_remembers_earlier_turns(db):
    llm = RoutingLLM("research")
    compiled = build_graph(StubRetriever(), db, llm)
    ask(compiled, "first question", thread_id="t1")
    state = ask(compiled, "second question", thread_id="t1")
    assert state["question"] == "second question"
    assert state["documents"]
