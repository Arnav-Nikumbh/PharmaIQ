# PharmaIQ Phase 1 — Internal Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project skeleton and a seeded, read-only, guarded SQLite database with a Northwind table shape and plain-language pharmaceutical business data.

**Architecture:** `database/schema.py` owns the DDL and a deterministic seeder. `database/db_manager.py` owns a read-only connection plus two operations the agents will later need: render the schema for a prompt, and safely execute a SELECT. Safety is two-layered: a validator that rejects anything that is not a single read query, and a genuinely read-only SQLite connection behind it.

**Tech Stack:** Python 3.12 (via `uv`), stdlib `sqlite3`, `python-dotenv`, `pytest`.

**Commit policy for this repo:** every `git commit` step below requires the user's explicit approval for that specific commit. Do not commit without asking. This repo has no remote and nothing is pushed.

---

### Task 1: Project skeleton and tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config.py`
- Create: `database/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "pharmaiq"
version = "0.1.0"
description = "Agentic commercial intelligence assistant for the life-sciences domain"
requires-python = ">=3.12"
dependencies = [
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "llm: requires a live Groq API key and network access",
]
addopts = "-m 'not llm'"

[tool.uv]
package = false
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
data/
chroma_db/
.DS_Store
```

- [ ] **Step 3: Create `.env.example`**

Note the file contains a placeholder only. Never write a real key into any tracked file.

```bash
# Copy to .env and paste your own personal Groq key from console.groq.com
# .env is gitignored and must never be committed.
GROQ_API_KEY=your-groq-key-here
```

- [ ] **Step 4: Create `config.py`**

```python
"""Central paths and settings. Import this rather than hardcoding paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "pharmaiq.db"
CHROMA_DIR = ROOT / "chroma_db"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Maximum rows any generated query may return.
SQL_ROW_LIMIT = 200

DATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 5: Create package markers**

```bash
mkdir -p database tests
touch database/__init__.py tests/__init__.py
```

- [ ] **Step 6: Create the virtual environment and install**

Run:

```bash
uv sync --python 3.12
```

Expected: uv downloads CPython 3.12 if absent, creates `.venv/`, installs `python-dotenv` and `pytest`.

- [ ] **Step 7: Verify the toolchain**

Run:

```bash
uv run python -c "import sys, dotenv; print(sys.version_info[:2])"
```

Expected: `(3, 12)`

- [ ] **Step 8: Ask the user for approval, then commit**

```bash
git add pyproject.toml uv.lock .gitignore .env.example config.py database/__init__.py tests/__init__.py
git commit -m "add project skeleton and tooling"
```

Confirm `git status` shows no `.env` and no `data/` staged.

---

### Task 2: Database schema DDL

**Files:**
- Create: `database/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

`tests/test_schema.py`:

```python
import sqlite3

from database.schema import TABLES, create_tables


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_schema.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'database.schema'`

- [ ] **Step 3: Write `database/schema.py`**

```python
"""Table definitions for the internal business database.

The table and column names deliberately follow the Northwind sample database's
shape and casing. The rows seeded into them are synthetic pharmaceutical
commercial data. Nothing here is real business data of any kind.
"""

import sqlite3

TABLES = (
    "Categories",
    "Region",
    "Territories",
    "Employees",
    "EmployeeTerritories",
    "Customers",
    "Products",
    "Orders",
    "OrderDetails",
)

DDL = """
CREATE TABLE Categories (
    CategoryID   INTEGER PRIMARY KEY,
    CategoryName TEXT NOT NULL,
    Description  TEXT
);

CREATE TABLE Region (
    RegionID          INTEGER PRIMARY KEY,
    RegionDescription TEXT NOT NULL
);

CREATE TABLE Territories (
    TerritoryID          TEXT PRIMARY KEY,
    TerritoryDescription TEXT NOT NULL,
    RegionID             INTEGER NOT NULL REFERENCES Region(RegionID)
);

CREATE TABLE Employees (
    EmployeeID INTEGER PRIMARY KEY,
    LastName   TEXT NOT NULL,
    FirstName  TEXT NOT NULL,
    Title      TEXT,
    HireDate   TEXT
);

CREATE TABLE EmployeeTerritories (
    EmployeeID  INTEGER NOT NULL REFERENCES Employees(EmployeeID),
    TerritoryID TEXT NOT NULL REFERENCES Territories(TerritoryID),
    PRIMARY KEY (EmployeeID, TerritoryID)
);

CREATE TABLE Customers (
    CustomerID   TEXT PRIMARY KEY,
    CompanyName  TEXT NOT NULL,
    ContactName  TEXT,
    ContactTitle TEXT,
    City         TEXT,
    TerritoryID  TEXT REFERENCES Territories(TerritoryID),
    Country      TEXT
);

CREATE TABLE Products (
    ProductID    INTEGER PRIMARY KEY,
    ProductName  TEXT NOT NULL,
    CategoryID   INTEGER NOT NULL REFERENCES Categories(CategoryID),
    UnitPrice    REAL NOT NULL,
    Discontinued INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE Orders (
    OrderID     INTEGER PRIMARY KEY,
    CustomerID  TEXT NOT NULL REFERENCES Customers(CustomerID),
    EmployeeID  INTEGER NOT NULL REFERENCES Employees(EmployeeID),
    OrderDate   TEXT NOT NULL,
    TerritoryID TEXT NOT NULL REFERENCES Territories(TerritoryID)
);

CREATE TABLE OrderDetails (
    OrderID   INTEGER NOT NULL REFERENCES Orders(OrderID),
    ProductID INTEGER NOT NULL REFERENCES Products(ProductID),
    UnitPrice REAL NOT NULL,
    Quantity  INTEGER NOT NULL,
    Discount  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (OrderID, ProductID)
);
"""


def create_tables(conn: sqlite3.Connection) -> None:
    """Drop and recreate every table. Safe to call repeatedly."""
    for table in reversed(TABLES):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(DDL)
    conn.commit()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_schema.py -v`
Expected: 3 passed

- [ ] **Step 5: Ask the user for approval, then commit**

```bash
git add database/schema.py tests/test_schema.py
git commit -m "add internal database schema"
```

---

### Task 3: Deterministic seed data

**Files:**
- Modify: `database/schema.py` (append the seeder)
- Modify: `tests/test_schema.py` (append seeder tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema.py`:

```python
from database.schema import seed


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_schema.py -v`
Expected: the eight new tests FAIL with `ImportError: cannot import name 'seed'`

- [ ] **Step 3: Append the seeder to `database/schema.py`**

```python
import random
from datetime import date, timedelta

SEED = 42

CATEGORIES = [
    ("Weight Management", "Treatments that support weight loss and obesity care"),
    ("Diabetes Care", "Treatments for blood sugar control"),
    ("Heart Health", "Treatments for blood pressure and cholesterol"),
    ("Cancer Care", "Treatments used in cancer therapy"),
    ("Respiratory", "Treatments for asthma and lung conditions"),
    ("Mental Health", "Treatments for mood, anxiety and sleep"),
    ("Pain Relief", "Treatments for short and long term pain"),
    ("Infection Control", "Antibiotic and antiviral treatments"),
    ("Bone and Joint", "Treatments for arthritis and bone density"),
    ("Skin Care", "Treatments for skin conditions"),
]

REGIONS = ["North", "South", "East", "West"]

TERRITORY_NAMES = [
    "Boston", "Hartford", "Buffalo", "Pittsburgh", "Cleveland",
    "Atlanta", "Orlando", "Nashville", "Charlotte", "New Orleans",
    "New York", "Philadelphia", "Baltimore", "Newark", "Richmond",
    "Denver", "Phoenix", "Seattle", "San Diego", "Portland",
]

# Territories are assigned to regions five at a time, in list order.

_PREFIXES = ["Ava", "Cardi", "Dermi", "Gluco", "Neuro", "Onco", "Pulmo", "Rheu", "Somni", "Vaso"]
_SUFFIXES = ["dex", "lex", "min", "nix", "prin", "sar", "tide", "vir", "zan", "zole"]

_CLINIC_KINDS = ["Clinic", "Medical Group", "Health Center", "Hospital", "Care Partners"]
_CITY_ADJECTIVES = ["Riverside", "Lakeview", "Summit", "Fairview", "Northgate", "Oakwood",
                    "Brookside", "Highland", "Parkway", "Westfield"]

_FIRST_NAMES = ["Alex", "Priya", "Jordan", "Mei", "Sam", "Ana", "Chris", "Nadia", "Ravi", "Elena"]
_LAST_NAMES = ["Reyes", "Patel", "Okafor", "Nguyen", "Silva", "Haddad", "Kim", "Novak",
               "Ibrahim", "Costa"]


def seed(conn: sqlite3.Connection) -> None:
    """Populate every table with deterministic synthetic data."""
    rng = random.Random(SEED)

    conn.executemany(
        "INSERT INTO Categories (CategoryID, CategoryName, Description) VALUES (?, ?, ?)",
        [(i + 1, name, desc) for i, (name, desc) in enumerate(CATEGORIES)],
    )

    conn.executemany(
        "INSERT INTO Region (RegionID, RegionDescription) VALUES (?, ?)",
        [(i + 1, name) for i, name in enumerate(REGIONS)],
    )

    territories = []
    for i, name in enumerate(TERRITORY_NAMES):
        territory_id = f"T{i + 1:03d}"
        region_id = (i // 5) + 1
        territories.append((territory_id, name, region_id))
    conn.executemany(
        "INSERT INTO Territories (TerritoryID, TerritoryDescription, RegionID) "
        "VALUES (?, ?, ?)",
        territories,
    )

    employees = []
    for i in range(10):
        employees.append((
            i + 1,
            _LAST_NAMES[i],
            _FIRST_NAMES[i],
            "Sales Representative",
            (date(2020, 1, 6) + timedelta(days=97 * i)).isoformat(),
        ))
    conn.executemany(
        "INSERT INTO Employees (EmployeeID, LastName, FirstName, Title, HireDate) "
        "VALUES (?, ?, ?, ?, ?)",
        employees,
    )

    # Each rep covers two territories; every territory has exactly one rep.
    emp_territories = []
    for i, (territory_id, _, _) in enumerate(territories):
        emp_territories.append(((i % 10) + 1, territory_id))
    conn.executemany(
        "INSERT INTO EmployeeTerritories (EmployeeID, TerritoryID) VALUES (?, ?)",
        emp_territories,
    )

    products = []
    used_names = set()
    for i in range(60):
        while True:
            name = (
                f"{rng.choice(_PREFIXES)}{rng.choice(_SUFFIXES)} "
                f"{rng.choice([5, 10, 25, 50, 100, 250])}mg"
            )
            if name not in used_names:
                used_names.add(name)
                break
        products.append((
            i + 1,
            name,
            (i % 10) + 1,
            round(rng.uniform(12.0, 480.0), 2),
            1 if rng.random() < 0.05 else 0,
        ))
    conn.executemany(
        "INSERT INTO Products (ProductID, ProductName, CategoryID, UnitPrice, Discontinued) "
        "VALUES (?, ?, ?, ?, ?)",
        products,
    )

    customers = []
    for i in range(90):
        territory_id, city, _ = territories[i % len(territories)]
        customers.append((
            f"C{i + 1:04d}",
            f"{rng.choice(_CITY_ADJECTIVES)} {rng.choice(_CLINIC_KINDS)}",
            f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
            rng.choice(["Physician", "Pharmacy Lead", "Procurement Manager",
                        "Clinical Director"]),
            city,
            territory_id,
            "USA",
        ))
    conn.executemany(
        "INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, "
        "City, TerritoryID, Country) VALUES (?, ?, ?, ?, ?, ?, ?)",
        customers,
    )

    territory_rep = {t_id: emp_id for emp_id, t_id in emp_territories}
    start = date(2024, 10, 1)
    orders = []
    details = []
    for order_id in range(1, 3001):
        customer = customers[rng.randrange(len(customers))]
        customer_id, territory_id = customer[0], customer[5]
        order_date = start + timedelta(days=rng.randrange(730))
        orders.append((
            order_id,
            customer_id,
            territory_rep[territory_id],
            order_date.isoformat(),
            territory_id,
        ))
        for product_id in rng.sample(range(1, 61), rng.randint(1, 4)):
            unit_price = products[product_id - 1][3]
            details.append((
                order_id,
                product_id,
                unit_price,
                rng.randint(1, 40),
                rng.choice([0.0, 0.0, 0.0, 0.05, 0.10]),
            ))
    conn.executemany(
        "INSERT INTO Orders (OrderID, CustomerID, EmployeeID, OrderDate, TerritoryID) "
        "VALUES (?, ?, ?, ?, ?)",
        orders,
    )
    conn.executemany(
        "INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) "
        "VALUES (?, ?, ?, ?, ?)",
        details,
    )

    conn.commit()
```

Move the `import random` and `from datetime import ...` lines to the top of the file
alongside `import sqlite3`, so all imports sit together.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_schema.py -v`
Expected: 11 passed

- [ ] **Step 5: Ask the user for approval, then commit**

```bash
git add database/schema.py tests/test_schema.py
git commit -m "add deterministic seed data for internal database"
```

---

### Task 4: SQL safety validator

**Files:**
- Create: `database/sql_guard.py`
- Test: `tests/test_sql_guard.py`

Kept in its own module because it is pure logic with no database dependency, which
makes it easy to test exhaustively.

- [ ] **Step 1: Write the failing tests**

`tests/test_sql_guard.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_sql_guard.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'database.sql_guard'`

- [ ] **Step 3: Write `database/sql_guard.py`**

```python
"""Validation for LLM-generated SQL.

This is the first of two defences. The second is that the database connection
itself is opened read-only, so a gap here still cannot mutate data.
"""

import re

FORBIDDEN = (
    "drop", "delete", "update", "insert", "alter", "create",
    "replace", "attach", "detach", "pragma", "vacuum", "reindex",
)

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


class UnsafeSQLError(Exception):
    """Raised when a query is not a single, read-only statement."""


def _strip_comments(sql: str) -> str:
    return _BLOCK_COMMENT.sub(" ", _LINE_COMMENT.sub(" ", sql))


def validate_select(sql: str) -> None:
    """Raise UnsafeSQLError unless `sql` is one read-only statement."""
    stripped = _strip_comments(sql).strip()
    if not stripped:
        raise UnsafeSQLError("The query is empty.")

    body = stripped.rstrip(";").strip()
    if ";" in body:
        raise UnsafeSQLError("Only one statement is allowed per query.")

    first = body.split(None, 1)[0].lower()
    if first not in ("select", "with"):
        raise UnsafeSQLError(
            f"Only SELECT and WITH queries are allowed. This one starts with '{first}'."
        )

    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", body, re.IGNORECASE):
            raise UnsafeSQLError(f"The keyword '{word.upper()}' is not allowed.")


def ensure_limit(sql: str, limit: int) -> str:
    """Append a LIMIT when the query has none. Assumes `sql` already validated."""
    body = _strip_comments(sql).strip().rstrip(";").strip()
    if re.search(r"\blimit\b", body, re.IGNORECASE):
        return body
    return f"{body} LIMIT {limit}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_sql_guard.py -v`
Expected: 21 passed

If `test_column_names_containing_keywords_are_not_rejected` fails, that is the expected
tension in this design: the word-boundary check rejects a column literally named
`UpdatedBy` only if the pattern is wrong. `\bupdate\b` does not match inside `UpdatedBy`,
so it should pass. Do not loosen the pattern to fix any other failure.

- [ ] **Step 5: Ask the user for approval, then commit**

```bash
git add database/sql_guard.py tests/test_sql_guard.py
git commit -m "add sql safety validator"
```

---

### Task 5: Database manager

**Files:**
- Create: `database/db_manager.py`
- Test: `tests/test_db_manager.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_db_manager.py`:

```python
import pytest

from database.db_manager import DBManager, build_database
from database.sql_guard import UnsafeSQLError


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    build_database(path)
    return DBManager(path)


def test_execute_select_returns_dicts(db):
    rows = db.execute_select("SELECT CategoryID, CategoryName FROM Categories ORDER BY CategoryID")
    assert rows[0] == {"CategoryID": 1, "CategoryName": "Weight Management"}


def test_execute_select_applies_a_row_limit(db):
    rows = db.execute_select("SELECT OrderID FROM Orders", limit=5)
    assert len(rows) == 5


def test_execute_select_rejects_mutations(db):
    with pytest.raises(UnsafeSQLError):
        db.execute_select("DELETE FROM Products")


def test_connection_is_read_only(db):
    # Bypass the validator to prove the connection itself refuses writes.
    import sqlite3
    with pytest.raises(sqlite3.OperationalError):
        db._connect().execute("DELETE FROM Products")


def test_get_schema_lists_every_table_and_sample_rows(db):
    schema = db.get_schema()
    assert "CREATE TABLE Products" in schema
    assert "ProductName" in schema
    assert "Sample rows" in schema


def test_a_realistic_analytics_query_runs(db):
    rows = db.execute_select("""
        SELECT r.RegionDescription, SUM(d.UnitPrice * d.Quantity * (1 - d.Discount)) AS TotalSales
        FROM OrderDetails d
        JOIN Orders o ON o.OrderID = d.OrderID
        JOIN Territories t ON t.TerritoryID = o.TerritoryID
        JOIN Region r ON r.RegionID = t.RegionID
        GROUP BY r.RegionDescription
        ORDER BY TotalSales DESC
    """)
    assert len(rows) == 4
    assert rows[0]["TotalSales"] > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_db_manager.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'database.db_manager'`

- [ ] **Step 3: Write `database/db_manager.py`**

```python
"""Read-only access to the internal business database."""

import sqlite3
from pathlib import Path

import config
from database.schema import TABLES, create_tables, seed
from database.sql_guard import ensure_limit, validate_select

SAMPLE_ROWS = 3


def build_database(path: Path) -> None:
    """Create and seed the database file, replacing any existing one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        create_tables(conn)
        seed(conn)
    finally:
        conn.close()


class DBManager:
    """Opens the database read-only and answers schema and query requests."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or config.DB_PATH)
        if not self.path.exists():
            raise FileNotFoundError(
                f"No database at {self.path}. Run: uv run python -m database.build"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def get_schema(self) -> str:
        """Render the schema plus sample rows as text for an LLM prompt."""
        parts: list[str] = []
        conn = self._connect()
        try:
            for table in TABLES:
                ddl = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if ddl is None:
                    continue
                parts.append(ddl["sql"].strip() + ";")
                rows = conn.execute(
                    f"SELECT * FROM {table} LIMIT {SAMPLE_ROWS}"
                ).fetchall()
                if rows:
                    parts.append(f"-- Sample rows from {table}:")
                    for row in rows:
                        parts.append("--   " + str(dict(row)))
                parts.append("")
        finally:
            conn.close()
        return "\n".join(parts)

    def execute_select(self, sql: str, limit: int | None = None) -> list[dict]:
        """Validate, limit and run a read query. Raises UnsafeSQLError if unsafe."""
        validate_select(sql)
        safe_sql = ensure_limit(sql, limit or config.SQL_ROW_LIMIT)
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute(safe_sql).fetchall()]
        finally:
            conn.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_db_manager.py -v`
Expected: 6 passed

- [ ] **Step 5: Ask the user for approval, then commit**

```bash
git add database/db_manager.py tests/test_db_manager.py
git commit -m "add read-only database manager"
```

---

### Task 6: Build command and manual verification

**Files:**
- Create: `database/build.py`

- [ ] **Step 1: Write `database/build.py`**

```python
"""Create the local database file. Run: uv run python -m database.build"""

import config
from database.db_manager import DBManager, build_database


def main() -> None:
    build_database(config.DB_PATH)
    db = DBManager(config.DB_PATH)
    rows = db.execute_select(
        "SELECT c.CategoryName, ROUND(SUM(d.UnitPrice * d.Quantity * (1 - d.Discount)), 2) AS TotalSales "
        "FROM OrderDetails d "
        "JOIN Products p ON p.ProductID = d.ProductID "
        "JOIN Categories c ON c.CategoryID = p.CategoryID "
        "GROUP BY c.CategoryName ORDER BY TotalSales DESC"
    )
    print(f"Database built at {config.DB_PATH}")
    print("Total sales by therapy area:")
    for row in rows:
        print(f"  {row['CategoryName']:<20} {row['TotalSales']:>12,.2f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Build the database and read the output**

Run: `uv run python -m database.build`
Expected: the path is printed, followed by ten therapy areas with non-zero totals in
descending order.

- [ ] **Step 3: Run the whole suite**

Run: `uv run pytest -v`
Expected: every test green (38 at the time of writing). Report the real number; if anything fails, say so.

- [ ] **Step 4: Confirm nothing private is tracked**

Run: `git status --short && git check-ignore -v data/pharmaiq.db`
Expected: `data/pharmaiq.db` is reported as ignored by `.gitignore`, and no `.env` or
`data/` entry appears in `git status`.

- [ ] **Step 5: Ask the user for approval, then commit**

```bash
git add database/build.py
git commit -m "add database build command"
```

---

## Phase 1 Done When

- `uv run pytest` passes with every test green.
- `uv run python -m database.build` prints sales by therapy area.
- `.env` and `data/` are untracked and ignored.
- The user has reviewed the seeded data and the guard behaviour before Phase 2 starts.
