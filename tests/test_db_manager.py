import sqlite3

import pytest

from database.db_manager import DBManager, build_database
from database.sql_guard import UnsafeSQLError


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    build_database(path)
    return DBManager(path)


def test_execute_select_returns_dicts(db):
    rows = db.execute_select(
        "SELECT CategoryID, CategoryName FROM Categories ORDER BY CategoryID"
    )
    assert rows[0] == {"CategoryID": 1, "CategoryName": "Weight Management"}


def test_execute_select_applies_a_row_limit(db):
    rows = db.execute_select("SELECT OrderID FROM Orders", limit=5)
    assert len(rows) == 5


def test_execute_select_rejects_mutations(db):
    with pytest.raises(UnsafeSQLError):
        db.execute_select("DELETE FROM Products")


def test_connection_is_read_only(db):
    # Bypass the validator to prove the connection itself refuses writes.
    with pytest.raises(sqlite3.OperationalError):
        db._connect().execute("DELETE FROM Products")


def test_get_schema_lists_every_table_and_sample_rows(db):
    schema = db.get_schema()
    assert "CREATE TABLE Products" in schema
    assert "ProductName" in schema
    assert "Sample rows" in schema


def test_missing_database_file_is_reported_clearly(tmp_path):
    with pytest.raises(FileNotFoundError):
        DBManager(tmp_path / "nope.db")


def test_a_realistic_analytics_query_runs(db):
    rows = db.execute_select("""
        SELECT r.RegionDescription,
               SUM(d.UnitPrice * d.Quantity * (1 - d.Discount)) AS TotalSales
        FROM OrderDetails d
        JOIN Orders o ON o.OrderID = d.OrderID
        JOIN Territories t ON t.TerritoryID = o.TerritoryID
        JOIN Region r ON r.RegionID = t.RegionID
        GROUP BY r.RegionDescription
        ORDER BY TotalSales DESC
    """)
    assert len(rows) == 4
    assert rows[0]["TotalSales"] > 0


def test_the_read_only_uri_is_properly_escaped(tmp_path):
    """A path with a space must still open. Windows paths need this too."""
    folder = tmp_path / "a folder with spaces"
    folder.mkdir()
    path = folder / "spaced.db"
    build_database(path)
    db = DBManager(path)
    assert db.execute_select("SELECT COUNT(*) AS n FROM Products")[0]["n"] == 60


def test_the_connection_uri_has_no_raw_separator_problems(tmp_path):
    path = tmp_path / "uri check" / "u.db"
    build_database(path)
    uri = f"{DBManager(path).path.resolve().as_uri()}?mode=ro"
    assert uri.startswith("file:///")
    assert " " not in uri
    assert "\\" not in uri
