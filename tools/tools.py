"""The three data-access operations, as plain functions.

The graph calls these directly. server.py exposes the same three over MCP.
Keeping the logic here means there is one implementation, not two.
"""

import config
from database.db_manager import DBManager
from retrieval.vector_store import HybridRetriever

_retriever: HybridRetriever | None = None
_db: DBManager | None = None


def get_retriever() -> HybridRetriever:
    """Open the search index once and reuse it."""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def get_db() -> DBManager:
    """Open the database once and reuse it."""
    global _db
    if _db is None:
        _db = DBManager(config.DB_PATH)
    return _db


def search_research_documents(query: str, k: int = 6, source: str | None = None) -> list[dict]:
    """Search clinical trials and papers. `source` limits it to one of them."""
    filters = {"source": source} if source else None
    return get_retriever().search(query, k=k, filters=filters)


def get_database_schema() -> str:
    """Return the sales database schema, with sample rows."""
    return get_db().get_schema()


def execute_sql_query(sql: str) -> list[dict]:
    """Run one read-only SELECT against the sales database."""
    return get_db().execute_select(sql)
