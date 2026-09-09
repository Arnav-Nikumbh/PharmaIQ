"""MCP server exposing PharmaIQ's data access.

Run: uv run python server.py

This is a thin wrapper. The functions it exposes are the same ones the graph
calls, so an MCP client and the app always see identical behaviour.
"""

from fastmcp import FastMCP

from tools import tools

mcp = FastMCP("PharmaIQ")


@mcp.tool
def search_research_documents(query: str, k: int = 6, source: str | None = None) -> list[dict]:
    """Search clinical trials and published papers for a topic.

    Args:
        query: what to search for
        k: how many chunks to return
        source: limit to "clinicaltrials" or "pubmed", or leave unset for both
    """
    return tools.search_research_documents(query, k=k, source=source)


@mcp.tool
def get_database_schema() -> str:
    """Return the internal sales database schema, with sample rows."""
    return tools.get_database_schema()


@mcp.tool
def execute_sql_query(sql: str) -> list[dict]:
    """Run one read-only SELECT against the internal sales database.

    Anything that is not a single read query is rejected.
    """
    return tools.execute_sql_query(sql)


if __name__ == "__main__":
    mcp.run()
