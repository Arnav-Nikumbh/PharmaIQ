import pytest

from database.db_manager import build_database
from database.sql_guard import UnsafeSQLError
from tools import tools


class StubRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query, k=10, filters=None):
        self.calls.append((query, k, filters))
        return [{"chunk_id": "pubmed:1:0", "text": "x", "metadata": {}}]


@pytest.fixture(autouse=True)
def wired(tmp_path, monkeypatch):
    """Point the tool layer at a temporary database and a stub retriever."""
    path = tmp_path / "tools.db"
    build_database(path)
    monkeypatch.setattr(tools.config, "DB_PATH", path)
    monkeypatch.setattr(tools, "_db", None)
    retriever = StubRetriever()
    monkeypatch.setattr(tools, "_retriever", retriever)
    return retriever


def test_search_passes_the_query_through(wired):
    tools.search_research_documents("weight loss", k=3)
    assert wired.calls[0] == ("weight loss", 3, None)


def test_search_turns_a_source_into_a_filter(wired):
    tools.search_research_documents("q", source="pubmed")
    assert wired.calls[0][2] == {"source": "pubmed"}


def test_schema_includes_the_tables():
    assert "CREATE TABLE Products" in tools.get_database_schema()


def test_a_select_returns_rows():
    rows = tools.execute_sql_query("SELECT CategoryName FROM Categories LIMIT 2")
    assert len(rows) == 2


def test_a_mutating_query_is_refused():
    with pytest.raises(UnsafeSQLError):
        tools.execute_sql_query("DROP TABLE Products")


def test_the_database_is_opened_only_once():
    first = tools.get_db()
    assert tools.get_db() is first
