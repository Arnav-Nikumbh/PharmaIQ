"""Fetch, cache and chunk research for one topic.

Run: uv run python -m ingestion.ingest --topic "obesity weight loss" --limit 25

Raw documents are cached under data/raw/ so the pipeline can be re-run
without hitting the APIs again. Pass --refresh to fetch afresh.
"""

import argparse
import json
import re
from pathlib import Path

import config
from ingestion.clinicaltrials import fetch_studies
from ingestion.processor import process_documents
from ingestion.pubmed import fetch_articles

FETCHERS = {"clinicaltrials": fetch_studies, "pubmed": fetch_articles}


def slugify(topic: str) -> str:
    """Turn a topic into a safe filename stem."""
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "topic"


def cache_path(source: str, topic: str) -> Path:
    return config.RAW_DIR / f"{source}_{slugify(topic)}.json"


def collect(topic: str, limit: int, sources: list[str], refresh: bool = False) -> list[dict]:
    """Return normalized documents for `topic`, using the cache when possible."""
    documents: list[dict] = []
    for source in sources:
        path = cache_path(source, topic)
        if path.exists() and not refresh:
            fetched = json.loads(path.read_text())
            print(f"  {source}: {len(fetched)} documents from cache")
        else:
            fetched = FETCHERS[source](topic, limit)
            path.write_text(json.dumps(fetched, indent=2))
            print(f"  {source}: {len(fetched)} documents fetched")
        documents.extend(fetched)
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest research for one topic.")
    parser.add_argument("--topic", required=True, help="what to search for")
    parser.add_argument("--limit", type=int, default=25, help="documents per source")
    parser.add_argument(
        "--source", choices=[*FETCHERS, "both"], default="both", help="which source to use"
    )
    parser.add_argument("--refresh", action="store_true", help="ignore the cache")
    args = parser.parse_args()

    sources = list(FETCHERS) if args.source == "both" else [args.source]
    print(f'Topic: "{args.topic}"')
    documents = collect(args.topic, args.limit, sources, args.refresh)

    chunks = process_documents(documents)
    out = config.DATA_DIR / f"chunks_{slugify(args.topic)}.json"
    out.write_text(json.dumps(chunks, indent=2))

    if chunks:
        sizes = [len(c["text"]) for c in chunks]
        print(f"\n{len(documents)} documents produced {len(chunks)} chunks")
        print(f"chunk size: min {min(sizes)}, average {sum(sizes) // len(sizes)}, max {max(sizes)}")
        print(f"saved to {out}")
    else:
        print("\nNo documents found for that topic.")


if __name__ == "__main__":
    main()
