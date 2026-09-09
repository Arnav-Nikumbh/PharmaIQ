"""Exercise the MCP server through a real client, in process."""

import asyncio
import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from database.db_manager import build_database
from server import mcp
from tools import tools


@pytest.fixture(autouse=True)
def wired(tmp_path, monkeypatch):
    path = tmp_path / "mcp.db"
    build_database(path)
    monkeypatch.setattr(tools.config, "DB_PATH", path)
    monkeypatch.setattr(tools, "_db", None)


def call(name, arguments=None):
    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool(name, arguments or {})
            return result.content[0].text
    return asyncio.run(run())


def listed():
    async def run():
        async with Client(mcp) as client:
            return [t.name for t in await client.list_tools()]
    return asyncio.run(run())


def test_the_three_tools_are_exposed():
    assert set(listed()) == {
        "search_research_documents", "get_database_schema", "execute_sql_query"
    }


def test_schema_comes_back_through_mcp():
    assert "CREATE TABLE Products" in call("get_database_schema")


def test_a_select_comes_back_through_mcp():
    rows = json.loads(call("execute_sql_query",
                           {"sql": "SELECT CategoryName FROM Categories LIMIT 2"}))
    assert rows[0]["CategoryName"] == "Weight Management"


def test_a_mutating_query_is_refused_through_mcp():
    # The guard raises, which fastmcp surfaces to the client as a tool error.
    with pytest.raises(ToolError):
        call("execute_sql_query", {"sql": "DROP TABLE Products"})


def test_a_refused_query_leaves_the_data_alone():
    with pytest.raises(ToolError):
        call("execute_sql_query", {"sql": "DELETE FROM Products"})
    rows = json.loads(call("execute_sql_query", {"sql": "SELECT COUNT(*) AS n FROM Products"}))
    assert rows[0]["n"] == 60
