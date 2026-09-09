# PharmaIQ — Design Spec

**Date:** 2026-09-09
**Status:** Approved for planning

## 1. Purpose

PharmaIQ is a learning project: an agentic commercial-intelligence assistant for the
life-sciences domain. It answers questions that need external pharmaceutical research
(ClinicalTrials.gov, PubMed) and internal structured business data at the same time.

The distinguishing behaviour is Path C: research retrieved from unstructured documents
determines *what internal data gets queried*. Retrieval influences the SQL, rather than
RAG and SQL being two independent features in one app.

This is a demo/learning project. It uses no Aeron credentials, no Aeron databases, and
no Infisical. Its one secret lives in a local, gitignored `.env`.

## 2. Scope

In scope: the ingestion to retrieval to context-extraction to SQL to synthesis pipeline,
orchestrated with LangGraph, exposed through Streamlit, with a FastMCP facade over the
three core data-access functions.

Out of scope for this iteration:

- Cross-encoder re-ranking (README marks it optional; the retrieval interface leaves a
  seam for it).
- PostgreSQL. SQLite only.
- Authentication, multi-user state, deployment.
- Any claim that the internal dataset is real pharmaceutical data.

## 3. Decisions

| Decision | Choice | Reason |
|---|---|---|
| Location | `~/RAG Proj/pharmaiq` | User's choice; git repo initialised there. |
| Python | 3.12 via `uv` | System Python is 3.9 (too old); 3.14 is ahead of chromadb support. |
| LLM | Groq, `llama-3.3-70b-versatile` | User's choice; free tier, fast, supports JSON mode. |
| Embeddings | Local `all-MiniLM-L6-v2` | Groq offers no embeddings API. CPU-local, free, ~80MB weights fetched on first run. |
| Internal DB | Northwind *shape*, locally seeded | Option A. No download, fully private, Northwind-style column names preserve the SQL self-correction exercise. |
| Tool layer | Plain functions; MCP as a facade | Graph nodes call functions directly (one process, easier to debug); `server.py` re-exports them over FastMCP. |
| Secrets | `.env`, gitignored, `GROQ_API_KEY` only | Explicit user instruction for this demo project. |

### 3.1 On the internal database

The README suggests remapping Northwind. Rather than downloading the real Northwind
dump (whose products are beverages and condiments, making every pharma answer fiction),
`database/schema.py` creates the Northwind *table structure* and seeds it with generated
pharma-flavoured rows.

Tables: `Categories`, `Products`, `Customers`, `Employees`, `Orders`, `OrderDetails`,
`Region`, `Territories`, `EmployeeTerritories`.

Conceptual mapping, stated in the SQL agent's system prompt:

```
Products      -> drug products (ProductName = brand, CategoryID = therapy class)
Categories    -> plain-language therapy areas (Weight Management, Diabetes Care, ...)
Customers     -> HCPs / clinics / hospital accounts
Employees     -> sales representatives
Orders        -> prescription/order events
OrderDetails  -> line-level units and revenue
Region        -> North / South / East / West
Territories   -> named territories inside a region
```

Column names stay Northwind-style (`ProductName`, `UnitPrice`, `CustomerID`). The casing
is deliberately not what an LLM guesses first, which keeps the Section 10 self-correction
loop meaningful rather than decorative.

Seed volume: roughly 10 categories, 60 products, 90 customers, 10 employees, 4 regions,
20 territories, and about 3,000 orders spanning 24 months, generated with a fixed random
seed so results are reproducible.

## 4. Architecture

```
Streamlit (app.py)
        |
        v
  LangGraph (graph.py)
  guardrail -> supervisor -> { rag | sql | rag_then_sql } -> synthesis
        |                              |
        v                              v
   agents/*.py                    tools/tools.py
        |                         /            \
        v                        v              v
 agents/context_extractor  HybridRetriever  DBManager
                                |               |
                                v               v
                           ChromaDB         SQLite
                                ^
                                |
                          ingestion/*.py  <- ClinicalTrials.gov, PubMed
```

`server.py` (FastMCP) sits beside the graph and calls the same `tools/tools.py`
functions; it is not on the Streamlit request path.

## 5. Components

Each module has one purpose and an interface that can be understood without reading its
internals.

### 5.1 `database/`

- **`schema.py`** — DDL constants and `seed(conn)`. Deterministic (fixed seed). Idempotent:
  drops and recreates.
- **`db_manager.py`** — `DBManager` opening SQLite read-only (`file:...?mode=ro` URI).
  - `get_schema() -> str` — `CREATE TABLE` statements plus three sample rows per table,
    formatted for an LLM prompt.
  - `execute_select(sql) -> list[dict]` — validates then executes.

  Validation rejects: anything whose first keyword is not `SELECT` or `WITH`; any
  statement containing `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `REPLACE`,
  `ATTACH`, `PRAGMA`; multiple statements (a `;` other than a trailing one). A `LIMIT` is
  appended when absent (default 200). Read-only mode is the second line of defence, so a
  validator bug still cannot mutate data.

### 5.2 `ingestion/`

Both fetchers return the same normalized document dict:

```python
{
  "source": "clinicaltrials" | "pubmed",
  "document_id": str,      # NCT id or PMID
  "title": str,
  "text": str,
  "metadata": {"condition": str, "intervention": str, "date": str, "url": str, ...}
}
```

- **`clinicaltrials.py`** — ClinicalTrials.gov API v2 (`/api/v2/studies`), no key required.
  Flattens title, conditions, interventions, brief summary, eligibility, outcomes.
- **`pubmed.py`** — NCBI E-utilities `esearch` + `efetch`, no key required (rate limited to
  3 requests/second without one). Extracts title, abstract, journal, date, authors.
- **`processor.py`** — `clean_text`, `chunk_document` (about 800 characters, 100-character
  overlap, split on paragraph then sentence boundaries), and metadata attachment. Chunk ids
  are `{source}:{document_id}:{index}`, so re-ingesting the same topic overwrites rather
  than duplicates.
- **`ingest.py`** — CLI: `python -m ingestion.ingest --topic "weight loss obesity treatment" --limit 50`.
  Raw API responses are cached to `data/raw/` so the pipeline can be re-run without
  re-fetching.

### 5.3 `retrieval/vector_store.py`

One class, `HybridRetriever`:

- `add_chunks(chunks)` — embeds and upserts into a persistent Chroma collection, and
  rebuilds the BM25 index over the same corpus (persisted as a pickle next to the Chroma
  directory so a fresh process does not need to re-read every document).
- `search(query, k=10, filters=None) -> list[Chunk]` — runs dense and BM25 in parallel,
  each returning 30 candidates, applies metadata filters, fuses with RRF
  (`score = sum(1 / (60 + rank))`), returns the top k.

The optional re-ranker is a documented seam: a `rerank` hook that defaults to identity.

### 5.4 `agents/`

Each agent is a plain function taking the graph state and returning a state patch. None
of them import Streamlit or LangGraph internals, so all are testable directly.

- **`supervisor.py`** — classifies the question into `research` / `sql` / `cross` via a
  constrained JSON response. Falls back to `cross` on a malformed response.
- **`rag_agent.py`** — retrieves, answers from the retrieved chunks only, returns the
  answer plus numbered citations carrying source, document id, and URL.
- **`sql_agent.py`** — receives question, schema, and optional research context; generates
  SQL; validates; executes; on error, feeds the error message and schema back for up to
  two retries.
- **`synthesis_agent.py`** — composes the final answer in the three-part shape from README
  Section 14 (Research Findings / Internal Performance / Business Insight / Sources), and
  omits sections it has no data for.
- **`agents/context_extractor.py`** — the RAG-to-SQL bridge. Turns retrieved chunks into a
  structured object:

  ```json
  {
    "entities": {"therapy": [], "condition": [], "product_class": [], "regions": []},
    "insights": []
  }
  ```

  Extracted product classes are matched against actual `Categories.CategoryName` and
  `Products.ProductName` values in the database, so the SQL agent receives terms that
  exist rather than terms the model invented. Unmatched entities are kept but flagged, and
  the UI shows which mapped and which did not.

### 5.5 `graph.py`

State:

```python
{"messages": [], "route": "", "documents": [], "research_context": {},
 "sql_query": "", "sql_results": [], "citations": [], "answer": "", "errors": []}
```

Flow: `guardrail -> supervisor -> {rag, sql, rag_then_sql} -> synthesis -> END`.
The guardrail short-circuits off-topic questions straight to a fixed refusal message.
`MemorySaver` provides per-thread conversation memory.

### 5.6 `server.py`

FastMCP exposing `search_research_documents`, `get_database_schema`, and
`execute_sql_query` — the same functions the graph calls.

### 5.7 `app.py`

Streamlit chat. For each answer, expandable panels show route, citations, extracted
context (with matched-versus-unmatched entities), generated SQL, and the result table.

All user-facing strings avoid em dashes, per the global writing rule.

## 6. Error Handling

| Failure | Behaviour |
|---|---|
| Missing `GROQ_API_KEY` | Startup check with a clear message naming `.env`; Phases 1 to 4 still usable. |
| External API down or rate-limited | Retry with backoff, then skip that document and log; ingestion continues. |
| Empty retrieval | RAG agent says it found no relevant research rather than inventing an answer. |
| Invalid SQL | Up to two self-correction retries, then report the failure with the last error, honestly. |
| Rejected SQL (mutation attempt) | Blocked before execution, surfaced in the UI as a guard message. |
| Malformed LLM JSON | Each structured call has a defined fallback; nothing crashes the graph. |

## 7. Testing

Deterministic components get real unit tests:

- SQL guard: mutations, stacked statements, and comment-obfuscated variants are rejected;
  valid SELECT/WITH/JOIN queries pass; LIMIT injection works.
- RRF fusion: known input rankings produce the expected fused order.
- Chunker: boundaries, overlap, and stable chunk ids.
- Normalizers: recorded API fixtures produce the expected document dict, so tests never
  hit the network.
- Seeder: schema creates cleanly and row counts match expectations.

LLM-dependent nodes get one smoke test each, marked `@pytest.mark.llm` and deselected by
default, so `pytest` passes offline.

## 8. Build Order

Nine phases, following the README. Review checkpoint after each.

1. **Internal database** — `schema.py`, `db_manager.py`, seeder, SQL-guard tests.
2. **External ingestion** — `clinicaltrials.py`, `pubmed.py`, normalized output, fixtures.
3. **Document processing** — `processor.py`, chunking, metadata, `ingest.py` CLI.
4. **Vector store** — Chroma, BM25, RRF, `HybridRetriever`, retrieval tests.
5. **RAG agent** — grounded answers, citations. First phase needing the Groq key.
6. **SQL agent** — generation, validation, execution, self-correction.
7. **LangGraph** — guardrail, supervisor, three routes, context extraction, synthesis, memory.
8. **MCP** — FastMCP facade over the three tool functions.
9. **Streamlit** — chat UI with intermediate-step panels.

## 9. Repository Layout

```
pharmaiq/
├── agents/{supervisor,rag_agent,sql_agent,synthesis_agent,context_extractor,llm,parsing}.py
├── ingestion/{clinicaltrials,pubmed,processor,ingest}.py
├── retrieval/vector_store.py
├── tools/tools.py
├── database/{db_manager,schema}.py
├── graph.py
├── server.py
├── app.py
├── config.py
├── data/            # sqlite db + cached raw API responses (gitignored)
├── chroma_db/       # gitignored
├── tests/
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

`.gitignore` covers `.env`, `data/`, `chroma_db/`, `__pycache__/`, `.venv/`.

## 10. Risks

- **Groq JSON reliability.** Llama models sometimes wrap JSON in prose. Every structured
  call uses JSON mode where available plus a tolerant parser and a defined fallback.
- **Entity-to-schema mismatch.** The extractor may name therapies absent from the seeded
  catalogue. Mitigated by matching against real column values and by seeding the catalogue
  with therapy classes that match the demo topics (GLP-1, obesity, diabetes, oncology).
- **First-run latency.** Embedding weights download once, about 80MB. Called out in the
  README setup steps.

## 11. Language and Terminology

Anything a person reads (Streamlit labels, panel headings, error messages, README prose,
seeded category names, example questions) uses plain language. Readers are not assumed to
know pharmaceutical jargon.

- Seeded `Categories.CategoryName` values are everyday descriptions, not drug classes:
  `Weight Management`, `Diabetes Care`, `Heart Health`, `Cancer Care`, `Respiratory`,
  `Mental Health`, `Pain Relief`, `Infection Control`, `Bone and Joint`, `Skin Care`.
- UI panels are labelled in plain terms: "How the question was answered" rather than
  "Route", "What the research said" rather than "RAG output", "Database query" rather
  than "Generated SQL".
- Where a technical term is genuinely useful, it appears glossed on first use, for example
  "weight-loss therapies (the GLP-1 class)". Retrieved source documents keep their own
  wording untouched, since that is quoted evidence rather than our prose.
- Code identifiers, comments, and logs are unaffected.

No user-facing string contains an em dash, per the global writing rule.
