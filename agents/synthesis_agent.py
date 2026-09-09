"""Combine research evidence and internal numbers into one answer."""

import json

SYSTEM_PROMPT = """You write short business answers for a life-sciences company.

You are given what the research said and what our sales database returned.
Write the answer with only the headings that apply:

What the research says
What our data shows
What this suggests

Rules:
- Keep the research citation numbers, like [1], exactly as they appear.
- Quote real figures from the data. Never invent one.
- If the database query failed, say the numbers were not available and answer
  from the research alone.
- Write plainly. Explain any technical term the first time you use it.
- Do not use em dashes."""


def _sql_block(sql_result: dict | None) -> str:
    if not sql_result:
        return "No database query was run."
    if sql_result.get("error"):
        return f"The database query failed: {sql_result['error']}"
    rows = sql_result.get("results") or []
    if not rows:
        return "The database query returned no rows."
    return json.dumps(rows[:30], indent=2, default=str)


def _sources(citations: list[dict]) -> str:
    lines = [
        f"[{c['number']}] {c.get('title', '')} ({c.get('source', '')} {c.get('document_id', '')})"
        f" {c.get('url', '')}".rstrip()
        for c in citations
    ]
    return "\n\nSources\n" + "\n".join(lines)


def synthesize(question: str, rag_result: dict | None, sql_result: dict | None, llm) -> str:
    """Write the final answer and append the source list."""
    rag_result = rag_result or {}
    research = rag_result.get("answer") or "No research was consulted."

    user = (
        f"Question: {question}\n\n"
        f"What the research said:\n{research}\n\n"
        f"What the database returned:\n{_sql_block(sql_result)}"
    )
    reply = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])

    answer = reply.content.strip()
    citations = rag_result.get("citations") or []
    return answer + _sources(citations) if citations else answer
