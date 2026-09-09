import pytest

from database.sql_guard import UnsafeSQLError, ensure_limit, validate_select


@pytest.mark.parametrize("sql", [
    "SELECT * FROM Products",
    "select ProductName from Products where UnitPrice > 10",
    "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
    "SELECT p.ProductName, SUM(d.Quantity) FROM Products p "
    "JOIN OrderDetails d ON d.ProductID = p.ProductID GROUP BY p.ProductName",
    "SELECT * FROM Products;",
])
def test_valid_read_queries_are_accepted(sql):
    validate_select(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE Products",
    "DELETE FROM Products",
    "UPDATE Products SET UnitPrice = 0",
    "INSERT INTO Products VALUES (1, 'x', 1, 1.0, 0)",
    "ALTER TABLE Products ADD COLUMN x TEXT",
    "CREATE TABLE evil (id INTEGER)",
    "ATTACH DATABASE '/tmp/other.db' AS other",
    "PRAGMA table_info(Products)",
])
def test_mutating_statements_are_rejected(sql):
    with pytest.raises(UnsafeSQLError):
        validate_select(sql)


def test_stacked_statements_are_rejected():
    with pytest.raises(UnsafeSQLError):
        validate_select("SELECT 1; DROP TABLE Products")


def test_keyword_hidden_in_a_comment_is_rejected():
    with pytest.raises(UnsafeSQLError):
        validate_select("SELECT 1 /* harmless */; DELETE FROM Products")


def test_comments_alone_do_not_break_a_valid_query():
    validate_select("-- report query\nSELECT ProductName FROM Products")


def test_column_names_containing_keywords_are_not_rejected():
    validate_select("SELECT OrderDate, UpdatedBy FROM Orders")


def test_empty_query_is_rejected():
    with pytest.raises(UnsafeSQLError):
        validate_select("   ")


def test_ensure_limit_appends_when_missing():
    assert ensure_limit("SELECT * FROM Products", 200) == "SELECT * FROM Products LIMIT 200"


def test_ensure_limit_strips_a_trailing_semicolon():
    assert ensure_limit("SELECT * FROM Products;", 50) == "SELECT * FROM Products LIMIT 50"


def test_ensure_limit_leaves_an_existing_limit_alone():
    sql = "SELECT * FROM Products LIMIT 5"
    assert ensure_limit(sql, 200) == sql
