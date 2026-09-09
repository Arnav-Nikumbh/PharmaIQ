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
    "product_class": [], // the therapy area, in plain words, such as
                         // "Weight Management" or "Heart Health"
    "regions": []        // places, only if the extracts name any
  },
  "insights": []         // short plain statements of what the research found
}

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


def extract_context(chunks: list[dict], llm, db) -> dict:
    """Turn retrieved chunks into entities checked against the database."""
    if not chunks:
        return {**EMPTY, "matched": {"categories": [], "products": []}}

    extracts = "\n\n".join(c.get("text", "") for c in chunks)
    reply = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": extracts},
    ])
    parsed = parse_json_object(reply.content)
    if not parsed:
        return {**EMPTY, "matched": {"categories": [], "products": []}}

    entities = parsed.get("entities") or {}
    categories, products = _catalogue(db)

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
