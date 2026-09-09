"""SQL agent tests. A stub LLM stands in for Groq; the database is real."""

import pytest

from agents.sql_agent import extract_sql, run_sql
from database.db_manager import DBManager, build_database


class ScriptedLLM:
    """Returns each scripted reply in turn, recording the prompts it saw."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def invoke(self, messages):
        self.prompts.append(messages)
        reply = self.replies.pop(0) if self.replies else "SELECT 1"
        return type("Reply", (), {"content": reply})()


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("sqlagent") / "test.db"
    build_database(path)
    return DBManager(path)


def test_extract_sql_strips_a_fenced_block():
    assert extract_sql("```sql\nSELECT 1\n```") == "SELECT 1"


def test_extract_sql_strips_an_unlabelled_fence():
    assert extract_sql("```\nSELECT 1\n```") == "SELECT 1"


def test_extract_sql_handles_prose_around_the_query():
    text = "Here you go:\n```sql\nSELECT ProductName FROM Products\n```\nHope that helps."
    assert extract_sql(text) == "SELECT ProductName FROM Products"


def test_extract_sql_passes_bare_sql_through():
    assert extract_sql("  SELECT 1  ") == "SELECT 1"


def test_a_valid_query_runs_and_returns_rows(db):
    llm = ScriptedLLM("SELECT CategoryName FROM Categories ORDER BY CategoryID")
    result = run_sql("list the therapy areas", db, llm)
    assert result["error"] is None
    assert result["results"][0]["CategoryName"] == "Weight Management"
    assert result["attempts"] == 1


def test_the_schema_is_given_to_the_model(db):
    llm = ScriptedLLM("SELECT 1 AS x")
    run_sql("anything", db, llm)
    assert "CREATE TABLE Products" in str(llm.prompts[0])


def test_a_bad_column_name_is_corrected_on_retry(db):
    llm = ScriptedLLM(
        "SELECT product_name FROM Products",          # wrong: snake_case
        "SELECT ProductName FROM Products LIMIT 3",   # corrected
    )
    result = run_sql("list products", db, llm)
    assert result["error"] is None
    assert result["attempts"] == 2
    assert len(result["results"]) == 3


def test_the_database_error_is_shown_to_the_model_on_retry(db):
    llm = ScriptedLLM("SELECT product_name FROM Products", "SELECT ProductName FROM Products")
    run_sql("list products", db, llm)
    assert "no such column" in str(llm.prompts[1]).lower()


def test_it_gives_up_after_the_retry_budget(db):
    llm = ScriptedLLM(*["SELECT nope FROM Products"] * 5)
    result = run_sql("list products", db, llm, max_attempts=3)
    assert result["error"] is not None
    assert result["results"] == []
    assert result["attempts"] == 3


def test_a_mutating_query_is_blocked_and_never_executed(db):
    llm = ScriptedLLM("DELETE FROM Products", "SELECT ProductName FROM Products LIMIT 1")
    result = run_sql("remove everything", db, llm)
    assert result["error"] is None          # it recovered on the retry
    assert "DELETE" not in result["sql"].upper()
    assert db.execute_select("SELECT COUNT(*) AS n FROM Products")[0]["n"] == 60


def test_research_context_is_given_to_the_model(db):
    llm = ScriptedLLM("SELECT 1 AS x")
    context = {"entities": {"product_class": ["Weight Management"]}, "insights": ["works well"]}
    run_sql("how are those selling?", db, llm, research_context=context)
    assert "Weight Management" in str(llm.prompts[0])


def test_no_research_context_means_no_context_section(db):
    llm = ScriptedLLM("SELECT 1 AS x")
    run_sql("plain question", db, llm)
    assert "Research context" not in str(llm.prompts[0])
