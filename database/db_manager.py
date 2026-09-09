"""Read-only access to the internal business database."""

import sqlite3
from pathlib import Path

import config
from database.schema import TABLES, create_tables, seed
from database.sql_guard import ensure_limit, validate_select

SAMPLE_ROWS = 3


def build_database(path: Path) -> None:
    """Create and seed the database file, replacing any existing one."""
    path = Path(path)
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
                rows = conn.execute(f"SELECT * FROM {table} LIMIT {SAMPLE_ROWS}").fetchall()
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
