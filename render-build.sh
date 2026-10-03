#!/usr/bin/env bash
# Render build step. data/ and chroma_db/ are not in the repository, so the
# sales database and the research index are generated here, at deploy time.
set -o errexit

uv sync --frozen --no-dev

uv run --no-sync python -m database.build
uv run --no-sync python -m ingestion.ingest --topic "obesity weight loss treatment" --limit 25
uv run --no-sync python -m ingestion.ingest --topic "type 2 diabetes treatment" --limit 25
uv run --no-sync python -m ingestion.ingest --topic "heart failure blood pressure cholesterol treatment" --limit 25
