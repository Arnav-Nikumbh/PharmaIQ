# PharmaIQ

An assistant that answers questions using published medical research, an
internal sales database, or both together.

**Live demo: [pharmaiq-syns.onrender.com](https://pharmaiq-syns.onrender.com)**
(free hosting, so the first visit after a quiet spell takes about a minute to
wake up)

A normal document assistant can tell you what the research says. A normal
database assistant can tell you what sold. PharmaIQ connects the two: it reads
the research first, pulls out the treatments and therapy areas it mentions,
checks those names against the product catalogue, and only then queries the
sales data. **What the research turns up decides what gets looked up.**

| Guide | For |
|---|---|
| This file | What it does and how it works |
| [WINDOWS_SETUP.md](WINDOWS_SETUP.md) | Running it on Windows, start to finish |
| [TEST_QUERIES.md](TEST_QUERIES.md) | Questions to try, with expected results |

## A learning project

Everything here is self-contained:

- The sales database is generated locally and is entirely made up. No real
  business data is involved.
- The only secret is a personal Groq key, kept in a local `.env` file that is
  never committed.
- Research comes from two free public APIs that need no key at all.

---

## Setup

On Windows, follow [WINDOWS_SETUP.md](WINDOWS_SETUP.md) instead, which covers
every step from installing the tools to testing in the browser.

```bash
uv sync
cp .env.example .env      # then paste your Groq key into .env
uv run python -m database.build
uv run python -m ingestion.ingest --topic "obesity weight loss treatment" --limit 25
uv run streamlit run app.py
```

Get a free key at [console.groq.com](https://console.groq.com). The first
ingest downloads a small embedding model, about 80MB, once.

### Deploying to Render

The live demo runs on Render. `render.yaml` describes the service. In the
Render dashboard choose **New > Blueprint**, pick this repository, and paste
your Groq key when asked for `GROQ_API_KEY`. `render-build.sh` installs dependencies, builds the
database and ingests the three starter topics on every deploy, since `data/`
and `chroma_db/` are not in the repository. Embeddings run through ONNX rather
than PyTorch, which keeps the app inside the free plan's 512MB of memory.

---

## How a question is answered

```
                    supervisor
                        |
    +---------+---------+---------+
    |         |         |         |
 off topic  research   data      both
    |         |         |         |
    |        RAG        |        RAG
    |         |         |         |
    |         |         |     extract what
    |         |         |     the research
    |         |         |     names
    |         |         |         |
    |         |        SQL <-- SQL, filtered
    |         |         |     by those names
    |         +----+----+---------+
    |              |
   reply       synthesis
```

One model call classifies the question into one of four routes. Off-topic
questions are turned away before any retrieval or query happens, so they cost
a single call. The **both** path is the reason the project exists.

---

## The ingestion pipeline

Turning two very different APIs into one searchable library.

```
ClinicalTrials.gov API v2        PubMed E-utilities
        |                                |
        +----------------+---------------+
                         |
                    normalize
                 (one document shape)
                         |
                   cache to disk
                     data/raw/
                         |
                       clean
              (control chars, whitespace)
                         |
                       chunk
            (paragraph, sentence, hard cut)
                         |
                   attach metadata
                (scalar values only)
                         |
              +----------+----------+
              |                     |
          embed into            tokenize for
          ChromaDB              BM25 keywords
```

### 1. Fetch

Both sources are public and unauthenticated.

- **ClinicalTrials.gov** (`ingestion/clinicaltrials.py`) uses API v2, paging 50
  studies at a time. It flattens the title, conditions, interventions, brief
  summary, primary outcomes and eligibility criteria into one block of text.
- **PubMed** (`ingestion/pubmed.py`) uses NCBI E-utilities: `esearch` for ids,
  then `efetch` in batches of 50 for the records. It parses the XML for the
  title, abstract, journal, authors and keywords. Abstracts often arrive in
  labelled sections, so `BACKGROUND`, `METHODS` and `RESULTS` are preserved
  rather than flattened into one run of text. A short delay between calls keeps
  within the roughly three requests per second allowed without a key.

### 2. Normalize

Both fetchers return the identical shape, so nothing downstream needs to know
where a document came from:

```python
{
  "source": "clinicaltrials" | "pubmed",
  "document_id": "NCT03788915" | "42710812",
  "title": "...",
  "text": "...",
  "metadata": {"condition": ..., "intervention": ..., "date": ..., "url": ...}
}
```

Two details that matter later:

- **Metadata values are scalars only.** ChromaDB rejects lists, so conditions
  and interventions are joined into comma separated strings here rather than
  failing at index time. A test enforces it.
- **Dates are normalized to `YYYY-MM-DD`.** PubMed writes months as names
  (`2026-Sep`) and ClinicalTrials writes numbers (`2018-04-16`). Left alone,
  date filtering and sorting would silently misbehave.

### 3. Cache

Raw responses are written to `data/raw/<source>_<topic>.json`. Re-running the
same topic reads from disk instead of hitting the APIs, which matters because
you will re-run ingestion while tuning retrieval, and PubMed rate limits
unauthenticated callers. Pass `--refresh` to force a new fetch.

### 4. Clean and chunk

`ingestion/processor.py` strips control characters, collapses runs of
whitespace, and keeps paragraph breaks. Then it splits each document into
chunks of at most **800 characters** with a **100 character overlap**.

Splitting degrades in three steps:

1. **Paragraphs.** The natural unit.
2. **Sentences**, when a paragraph is longer than the limit.
3. **A hard character cut**, when a single sentence still exceeds it.

That third step is not theoretical. Both sources contain long unpunctuated
blocks, eligibility criteria especially, that a sentence splitter cannot touch.
Without it one 5,000 character paragraph becomes one useless chunk.

Two further touches:

- **Every chunk is prefixed with its document title.** A chunk pulled from the
  middle of a study otherwise gives the model no idea what study it is from.
- **Chunk ids are `source:document_id:index`.** Re-ingesting a topic overwrites
  its chunks instead of duplicating them.

### 5. Index

Each chunk is embedded with **all-MiniLM-L6-v2**, running locally on CPU, and
upserted into a persistent ChromaDB collection in `chroma_db/`. Embeddings are
local because Groq serves chat models only and has no embeddings API. This
keeps the whole retrieval side free and offline after the model downloads once.

Run it:

```bash
uv run python -m ingestion.ingest --topic "type 2 diabetes treatment" --limit 25
```

---

## The retrieval pipeline

Biomedical questions mix meaning with exact terms. "Therapies that reduce body
weight" needs semantic matching. "NCT03788915" and "semaglutide" need exact
matching. One method cannot do both well, so both run and their rankings are
merged.

```
                       query
                         |
        +----------------+----------------+
        |                                 |
   dense search                      BM25 search
   (embeddings)                      (keywords)
   30 candidates                    30 candidates
        |                                 |
   metadata filter                  metadata filter
   (native in Chroma)               (applied after)
        |                                 |
        +----------------+----------------+
                         |
            reciprocal rank fusion (k=60)
                         |
                 diversity cap
              (max 2 chunks per document)
                         |
                   top k chunks
```

### Dense search

Embedding similarity, for when the question and the source use different words.
A search for "therapies that reduce body weight" finds text reading "patients
demonstrated significant weight-loss outcomes".

### BM25 keyword search

Classic lexical scoring over the same chunks, for exact domain terms: drug
names, trial ids, biomarkers. **The tokenizer keeps hyphens**, so `GLP-1` stays
one token instead of becoming `glp` and `1`, which is most of the point of
having BM25 in this domain.

The keyword index is rebuilt on demand from what is already in ChromaDB rather
than persisted separately. One less file to keep in sync with the corpus.

### Metadata filtering

Filters such as `{"source": "pubmed"}` are applied to **both** halves. ChromaDB
handles the dense side natively; BM25 knows nothing about metadata, so its
results are filtered afterwards against the same clause. Without that, a
filtered search would leak unfiltered keyword hits.

### Reciprocal rank fusion

The two rankings are not on a comparable scale, so scores cannot simply be
added. RRF merges by position instead:

```
score(d) = sum over lists of  1 / (60 + rank(d))
```

A chunk ranked well by both methods wins. A chunk found by only one still
appears, just lower. In practice the two lists overlap surprisingly little,
which is what makes fusion worth doing.

### Diversity cap

A single long paper can occupy every slot. After fusion, at most **2 chunks per
document** are kept. Chunks displaced by the cap are used to backfill, so a
small corpus still returns a full result set rather than a short one.

The effect on a real query:

```
before: 4 chunks from 2 distinct documents
after:  4 chunks from 3 distinct documents
```

The cap runs **after** fusion, never before, so it never interferes with
relevance ordering. Pass `max_per_document=0` to disable it.

---

## From research to SQL

This is the bridge, in `agents/context_extractor.py`, and the part that makes
the project more than two features in one app.

Retrieved chunks go to the model, which returns structured entities:

```json
{
  "entities": {
    "therapy": ["semaglutide"],
    "condition": ["obesity"],
    "product_class": ["Weight Management"],
    "regions": []
  },
  "insights": ["positive weight loss outcomes"]
}
```

**The catalogue's own therapy area names are put in the prompt** and the model
is told to copy them verbatim. Left to name them itself it produces near misses
such as "Diabetes Management" for `Diabetes Care`, which then fail to match and
get dropped, letting an incidental area drive the query instead. The user's
question goes in too, so extraction stays anchored to what was actually asked.

Whatever comes back is checked against real `Categories` and `Products` values.
Matched names are handed to the SQL agent. Unmatched ones are kept and shown in
the interface rather than silently discarded, because the research legitimately
names real drugs that do not exist in this made up catalogue.

---

## The SQL agent

The database keeps Northwind's table shape and capitalisation
(`ProductName`, `UnitPrice`), which is deliberately not what a model guesses
first. `agents/sql_agent.py` gets the schema with three sample rows per table,
plus a plain description of what each table means commercially.

**Wrong queries fix themselves.** When a query fails, the database's own error
message goes back to the model with the schema, and it tries again. Up to three
attempts. Blocked queries are reported the same way, so the agent can recover
from having attempted something it was not allowed to do.

**Queries cannot change anything.** Two independent mechanisms:

1. A validator rejects anything that is not one `SELECT` or `WITH` statement.
   It strips comments first, so a keyword cannot hide in one, and it rejects
   stacked statements.
2. The connection itself is opened read only, so even a gap in the validator
   cannot write.

A `LIMIT` is added when the query lacks one, capped at 200 rows.

---

## Writing the answer

`agents/synthesis_agent.py` composes the final reply under whichever of these
headings apply: what the research says, what our data shows, what this suggests.

Three rules exist because live testing showed they were needed:

- **Only the first 30 rows reach the prompt**, and the true row count is stated
  alongside them. Without that, a model shown 30 of 60 rows reports "the
  database contains 30 products" as fact.
- **No unsupported claims.** Where a pattern has no explanation in the material,
  the answer must say the reason is not visible in the data rather than invent
  one.
- **Em dashes are stripped in code.** The prompt asks the model not to use them
  and it uses them anyway.

Citations are numbered per document, not per chunk, and only sources the answer
actually cited are listed.

---

## Project layout

| Path | What it does |
|---|---|
| `database/schema.py` | Table definitions and the deterministic seed data |
| `database/sql_guard.py` | Rejects anything that is not a single read query |
| `database/db_manager.py` | Read only connection, schema rendering, execution |
| `ingestion/clinicaltrials.py` | Fetch and normalize studies |
| `ingestion/pubmed.py` | Fetch and normalize papers |
| `ingestion/processor.py` | Clean, chunk, attach metadata |
| `ingestion/ingest.py` | The ingest command, with caching |
| `retrieval/vector_store.py` | Dense plus BM25 plus RRF plus diversity |
| `agents/supervisor.py` | Routing, and the guardrail |
| `agents/rag_agent.py` | Grounded research answers with citations |
| `agents/context_extractor.py` | The bridge from research to database query |
| `agents/sql_agent.py` | Query writing, validation, self correction |
| `agents/synthesis_agent.py` | The final write up |
| `graph.py` | The workflow, with conversation memory |
| `tools/tools.py` | The three data operations |
| `server.py` | The same three, exposed over MCP |
| `app.py` | The web interface |

`data/` and `chroma_db/` are generated locally and are not in the repository.

---

## Tests

```bash
uv run pytest          # 171 tests, offline, no key needed
uv run pytest -m llm   # the few that call Groq for real
```

The offline suite needs no network and no API key. Fetchers are tested against
recorded API responses, retrieval against a fake embedding function, and the
agents against stub models. Tests that call Groq sit behind a marker and are
skipped by default.

Worth knowing what that split cannot catch. Every defect found during live
testing was invisible to the stubs: a model name that did not exist on the
account, the research agent answering the wrong half of a cross-source
question, ignored formatting instructions, invented explanations, and a
truncated result reported as a total. All prompt or configuration problems
rather than logic problems, which is the usual shape of bugs in this kind of
system.

---

## Model

Answers are generated by Groq. The default is `openai/gpt-oss-120b`, an
open-weights model Groq hosts. Set `GROQ_MODEL` in `.env` to change it. To see
what your key can reach:

```bash
uv run python -c "
import requests, config
r = requests.get('https://api.groq.com/openai/v1/models',
                 headers={'Authorization': f'Bearer {config.GROQ_API_KEY}'})
print(*sorted(m['id'] for m in r.json()['data']), sep='\n')"
```

Embeddings are local and independent of this.

---

## MCP server

The same three data operations are available to an MCP client such as Claude
Desktop:

```bash
uv run python server.py
```

It exposes `search_research_documents`, `get_database_schema` and
`execute_sql_query`. These are the identical functions the graph calls, so
there is one implementation rather than two, and the read only guarantees apply
equally.

---

## Known limitations

- **Research coverage is whatever you ingested.** Questions about a therapy
  area with no ingested research will correctly report finding nothing. That is
  the intended behaviour, not a failure.
- **Vague questions produce vague answers.** "How are we doing?" has produced a
  meaningless query. Name a therapy area, a region, or a metric.
- **Product names do not match their therapy area.** Names and categories are
  generated independently, so a product called `Cardidex` may sit under Weight
  Management. Cosmetic, and it affects no figure.
- **No re-ranker.** The retrieval stack stops at fusion and the diversity cap.
- **Free tier rate limits.** A cross-source question makes five model calls, so
  it uses the Groq allowance faster than a simple one.
