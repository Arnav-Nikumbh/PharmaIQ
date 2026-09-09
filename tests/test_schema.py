import sqlite3

from database.schema import TABLES, create_tables, seed


def test_create_tables_creates_every_expected_table():
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {row[0] for row in rows}
    assert names == set(TABLES)


def test_products_table_uses_northwind_column_names():
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(Products)")}
    assert {"ProductID", "ProductName", "CategoryID", "UnitPrice"} <= cols


def test_create_tables_is_idempotent():
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    create_tables(conn)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    assert len(rows) == len(TABLES)


def _seeded():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    seed(conn)
    return conn


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_seed_fills_every_table():
    conn = _seeded()
    for table in TABLES:
        assert _count(conn, table) > 0, f"{table} is empty"


def test_seed_row_counts_match_the_spec():
    conn = _seeded()
    assert _count(conn, "Categories") == 10
    assert _count(conn, "Region") == 4
    assert _count(conn, "Territories") == 20
    assert _count(conn, "Employees") == 10
    assert _count(conn, "Customers") == 90
    assert _count(conn, "Products") == 60
    assert _count(conn, "Orders") == 3000


def test_category_names_are_plain_language():
    conn = _seeded()
    names = {r["CategoryName"] for r in conn.execute("SELECT CategoryName FROM Categories")}
    assert "Weight Management" in names
    assert "Diabetes Care" in names
    assert "Heart Health" in names


def test_seed_is_deterministic():
    first = _seeded().execute(
        "SELECT ProductName FROM Products ORDER BY ProductID"
    ).fetchall()
    second = _seeded().execute(
        "SELECT ProductName FROM Products ORDER BY ProductID"
    ).fetchall()
    assert [r[0] for r in first] == [r[0] for r in second]


def test_every_order_has_at_least_one_line_item():
    conn = _seeded()
    orphans = conn.execute(
        "SELECT COUNT(*) FROM Orders o "
        "WHERE NOT EXISTS (SELECT 1 FROM OrderDetails d WHERE d.OrderID = o.OrderID)"
    ).fetchone()[0]
    assert orphans == 0


def test_foreign_keys_are_intact():
    conn = _seeded()
    conn.execute("PRAGMA foreign_keys = ON")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert violations == []


def test_orders_span_twenty_four_months():
    conn = _seeded()
    lo, hi = conn.execute("SELECT MIN(OrderDate), MAX(OrderDate) FROM Orders").fetchone()
    assert lo < hi
    assert lo.startswith("2024-")
    assert hi.startswith("2026-")
