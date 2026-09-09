"""The bridge from research documents to a database query.

The RAG agent must not hand the SQL agent a paragraph. It hands over named
entities. Those names come from the literature, which does not know what is
in our catalogue, so each one is checked against real values in the database.
The SQL agent then filters on terms that exist rather than terms the model
invented, and the interface shows which names matched and which did not.
"""

from agents.parsing import parse_json_object

SYSTEM_PROMPT = """Read the research extracts and pull out the business entities.

Reply with JSON only, in this shape:
{
  "entities": {
    "therapy": [],       // named treatments or drugs
    "condition": [],     // diseases or indications
    "product_class": [], // therapy areas, copied word for word from the list below
    "regions": []        // places, only if the extracts name any
  },
  "insights": []         // short plain statements of what the research found
}

The only therapy areas that exist in our catalogue are:
__CATEGORIES__

For product_class, copy names from that list exactly. Do not invent a name that
is not on it, and do not reword one. Include an area only if the user's question
is actually about it. If none of them fit, leave product_class empty.

Use only what the extracts say. Leave a list empty rather than guessing."""

EMPTY = {"entities": {}, "insights": [], "matched": {"categories": [], "products": []},
         "unmatched": []}


def _catalogue(db) -> tuple[dict, dict]:
    """Return lowercase lookups of therapy areas and product names."""
    categories = {
        row["CategoryName"].lower(): row["CategoryName"]
        for row in db.execute_select("SELECT CategoryName FROM Categories")
    }
    products = {
        row["ProductName"].lower(): row["ProductName"]
        for row in db.execute_select("SELECT ProductName FROM Products")
    }
    return categories, products


def extract_context(chunks: list[dict], llm, db, question: str = "") -> dict:
    """Turn retrieved chunks into entities checked against the database.

    The catalogue's own therapy area names go into the prompt. Left to invent
    them the model produces near misses like "Diabetes Management" for
    "Diabetes Care", which then fail to match and are dropped, letting an
    incidental area drive the query instead.
    """
    if not chunks:
        return {**EMPTY, "matched": {"categories": [], "products": []}}

    categories, products = _catalogue(db)
    # A plain replace, not .format: the prompt contains JSON braces.
    system = SYSTEM_PROMPT.replace(
        "__CATEGORIES__", "\n".join(f"- {name}" for name in sorted(categories.values()))
    )
    extracts = "\n\n".join(c.get("text", "") for c in chunks)
    user = f"The user asked: {question}\n\n{extracts}" if question else extracts
    reply = llm.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    parsed = parse_json_object(reply.content)
    if not parsed:
        return {**EMPTY, "matched": {"categories": [], "products": []}}

    entities = parsed.get("entities") or {}

    matched_categories: list[str] = []
    matched_products: list[str] = []
    unmatched: list[str] = []

    for name in [*entities.get("product_class", []), *entities.get("therapy", [])]:
        key = str(name).strip().lower()
        if key in categories:
            matched_categories.append(categories[key])
        elif key in products:
            matched_products.append(products[key])
        else:
            unmatched.append(str(name))

    return {
        "entities": entities,
        "insights": parsed.get("insights") or [],
        "matched": {"categories": matched_categories, "products": matched_products},
        "unmatched": unmatched,
    }
