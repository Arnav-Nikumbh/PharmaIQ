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
