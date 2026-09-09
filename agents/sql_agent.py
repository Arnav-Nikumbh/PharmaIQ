"""Turn a question, plus optional research context, into SQL and run it.

Generated SQL is often wrong on the first try, usually about column casing,
so a failed query is sent back to the model together with the database's own
error message. That is cheaper and more reliable than trying to prompt the
mistake away up front.
"""

import json
import re

from database.sql_guard import UnsafeSQLError

MAX_ATTEMPTS = 3

# The tables keep their Northwind names. This tells the model what they mean
# in business terms so it does not have to guess from column names alone.
TABLE_MEANINGS = """What the tables represent:
- Categories: therapy areas, in plain language (for example "Weight Management")
- Products: individual medicines. ProductName is the brand, CategoryID its therapy area
- Customers: clinics, hospitals and practices that place orders
- Employees: sales representatives
- Territories and Region: a territory sits inside one of four regions
- Orders: one order placed by a customer, handled by a representative
- OrderDetails: the line items of an order. Revenue is
  UnitPrice * Quantity * (1 - Discount)"""

SYSTEM_PROMPT = """You write SQLite queries for a pharmaceutical sales database.

{schema}

{meanings}

Rules:
- Return one SELECT query and nothing else. No explanation, no prose.
- Use the exact table and column names shown above, including their capitals.
- Never write DROP, DELETE, UPDATE, INSERT, ALTER or CREATE.
- Always name computed columns with AS.
- Add a LIMIT unless the query aggregates into a handful of rows."""

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_sql(text: str) -> str:
    """Pull the query out of a model reply that may be fenced or chatty."""
    match = _FENCE.search(text)
    return (match.group(1) if match else text).strip()


def _context_block(research_context: dict | None) -> str:
    if not research_context:
        return ""
    return (
        "\n\nResearch context from the literature. Use it to decide what to "
        "filter on, and match it to real values in the database:\n"
        + json.dumps(research_context, indent=2)
    )


def run_sql(
    question: str,
    db,
    llm,
    research_context: dict | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict:
    """Generate SQL, run it, and retry with the error message when it fails."""
    system = SYSTEM_PROMPT.format(schema=db.get_schema(), meanings=TABLE_MEANINGS)
    user = question + _context_block(research_context)

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    sql = ""
    error = None

    for attempt in range(1, max_attempts + 1):
        sql = extract_sql(llm.invoke(messages).content)
        try:
            rows = db.execute_select(sql)
            return {"sql": sql, "results": rows, "error": None, "attempts": attempt}
        except UnsafeSQLError as exc:
            error = f"That query was blocked: {exc}"
        except Exception as exc:
            error = str(exc)

        messages = messages[:2] + [
            {"role": "assistant", "content": sql},
            {
                "role": "user",
                "content": (
                    f"That query failed with: {error}\n\n"
                    "Look at the schema again, especially the exact column names "
                    "and their capitals, and return a corrected query."
                ),
            },
        ]

    return {"sql": sql, "results": [], "error": error, "attempts": max_attempts}
