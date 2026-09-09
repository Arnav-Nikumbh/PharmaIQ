"""Answer research questions from retrieved documents only.

The agent never answers from the model's own knowledge. If retrieval comes
back empty it says so rather than inventing an answer, which matters in a
domain where a confident wrong answer is worse than no answer.
"""

import re

NO_EVIDENCE = (
    "I could not find anything in the research library about that. "
    "Try ingesting research on that topic first."
)

SYSTEM_PROMPT = """You are a research assistant for the life-sciences domain.

Answer using ONLY the numbered sources below. Rules:
- Cite every claim with its source number, like [1] or [2].
- If the sources do not answer the question, say so plainly.
- Never use knowledge that is not in the sources.
- Write plainly. Assume the reader is not a clinician, so explain any
  technical term the first time you use it.
- Do not use em dashes.

Sources:
{context}"""

_CITED = re.compile(r"\[(\d+)\]")


def build_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    """Render chunks as numbered sources, one number per document."""
    numbers: dict[str, int] = {}
    citations: list[dict] = []
    blocks: list[str] = []

    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        document_id = metadata.get("document_id", "")
        if document_id not in numbers:
            numbers[document_id] = len(numbers) + 1
            citations.append({
                "number": numbers[document_id],
                "source": metadata.get("source", ""),
                "document_id": document_id,
                "title": metadata.get("title", ""),
                "url": metadata.get("url", ""),
                "date": metadata.get("date", ""),
            })
        blocks.append(f"[{numbers[document_id]}] {chunk.get('text', '')}")

    return "\n\n".join(blocks), citations


def answer_question(
    question: str,
    retriever,
    llm,
    k: int = 6,
    filters: dict | None = None,
) -> dict:
    """Retrieve, answer from what was retrieved, and return the citations used."""
    chunks = retriever.search(question, k=k, filters=filters)
    if not chunks:
        return {"answer": NO_EVIDENCE, "citations": [], "documents": []}

    context, citations = build_context(chunks)
    reply = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": question},
    ])
    answer = reply.content.strip()

    # Show only the sources the answer actually leant on. If it cited nothing,
    # keep them all rather than stripping the evidence away entirely.
    used = {int(n) for n in _CITED.findall(answer)}
    if used:
        citations = [c for c in citations if c["number"] in used]

    return {"answer": answer, "citations": citations, "documents": chunks}
