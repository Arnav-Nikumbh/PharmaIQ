"""Decide what a question needs before any work is done.

The guardrail is folded in here as the "off_topic" route. One model call
decides both whether the question belongs to this assistant and which path
should answer it, instead of paying for two.
"""

from agents.parsing import parse_json_object

ROUTES = ("research", "sql", "cross", "off_topic")
DEFAULT_ROUTE = "cross"

OFF_TOPIC_REPLY = (
    "I can help with pharmaceutical research and commercial questions about our "
    "products, sales and territories. Ask me something in that area and I will "
    "look it up."
)

SYSTEM_PROMPT = """Decide what a user's question needs. Reply with JSON only:
{"route": "<one of research, sql, cross, off_topic>"}

- research: answerable from published studies and papers alone.
  Example: "what do recent trials say about weight loss treatments?"
- sql: answerable from our internal sales database alone.
  Example: "which territories sold the most last quarter?"
- cross: needs the research first, then uses it to decide what to look up
  in our sales data. Example: "which treatments look promising, and how are
  our matching products selling?"
- off_topic: nothing to do with medical research or our commercial data.
  Example: "what is the weather today?"

When a question could be either research or cross, choose cross."""


def classify(question: str, llm) -> str:
    """Return one of ROUTES. Falls back to 'cross' when the reply makes no sense."""
    reply = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ])
    parsed = parse_json_object(reply.content) or {}
    route = str(parsed.get("route", "")).strip().lower()
    return route if route in ROUTES else DEFAULT_ROUTE
