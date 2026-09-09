"""Hybrid retrieval over the research corpus.

Two searches run over the same chunks and their rankings are merged:

  dense  - embeddings, good at meaning ("therapies that reduce body weight"
           finds "significant weight-loss outcomes")
  BM25   - keywords, good at exact terms (drug names, NCT ids, biomarkers)

Reciprocal Rank Fusion merges the two rankings without needing their scores
to be on the same scale.
"""

import re
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

import config

COLLECTION = "research"
RRF_K = 60
CANDIDATES = 30
_TOKEN = re.compile(r"[a-z0-9\-]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, keeping hyphens so terms like GLP-1 survive."""
    return _TOKEN.findall(text.lower())


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    """Merge ranked id lists into one. Appearing high in both lists wins."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


def _default_embedding_fn():
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


class HybridRetriever:
    """Stores chunks in ChromaDB and searches them with dense + BM25 + RRF."""

    def __init__(self, persist_dir: Path | None = None, embedding_fn=None) -> None:
        self.persist_dir = Path(persist_dir or config.CHROMA_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION,
            embedding_function=embedding_fn or _default_embedding_fn(),
        )
        self._bm25 = None
        self._bm25_ids: list[str] = []

    def count(self) -> int:
        return self.collection.count()

    def add_chunks(self, chunks: list[dict]) -> int:
        """Upsert chunks. Re-adding the same chunk_id overwrites rather than duplicates."""
        if not chunks:
            return 0
        self.collection.upsert(
            ids=[c["chunk_id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )
        self._bm25 = None  # the corpus changed, so the keyword index is stale
        return len(chunks)

    def _load_bm25(self) -> None:
        """Build the keyword index from what is already in Chroma.

        Rebuilding on demand avoids keeping a second copy of the corpus on disk.
        """
        stored = self.collection.get(include=["documents"])
        self._bm25_ids = stored["ids"]
        documents = stored["documents"] or []
        self._bm25 = BM25Okapi([tokenize(d) for d in documents]) if documents else None

    def _keyword_ranking(self, query: str, limit: int) -> list[str]:
        if self._bm25 is None:
            self._load_bm25()
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self._bm25_ids, scores), key=lambda pair: pair[1], reverse=True)
        return [chunk_id for chunk_id, score in ranked[:limit] if score > 0]

    def _dense_ranking(self, query: str, limit: int, where: dict | None) -> list[str]:
        result = self.collection.query(
            query_texts=[query],
            n_results=min(limit, max(self.count(), 1)),
            where=where or None,
        )
        return result["ids"][0] if result["ids"] else []

    def search(self, query: str, k: int = 10, filters: dict | None = None) -> list[dict]:
        """Return the top k chunks for `query`, optionally filtered by metadata."""
        if self.count() == 0:
            return []

        where = {key: {"$eq": value} for key, value in (filters or {}).items()}
        if len(where) > 1:
            where = {"$and": [{key: value} for key, value in where.items()]}

        dense = self._dense_ranking(query, CANDIDATES, where)
        keyword = self._keyword_ranking(query, CANDIDATES)
        if filters:
            # BM25 knows nothing about metadata, so filter its side afterwards.
            allowed = set(self.collection.get(where=where)["ids"])
            keyword = [chunk_id for chunk_id in keyword if chunk_id in allowed]

        ordered = reciprocal_rank_fusion([dense, keyword])[:k]
        if not ordered:
            return []

        stored = self.collection.get(ids=ordered, include=["documents", "metadatas"])
        by_id = {
            chunk_id: {"chunk_id": chunk_id, "text": text, "metadata": metadata}
            for chunk_id, text, metadata in zip(
                stored["ids"], stored["documents"], stored["metadatas"]
            )
        }
        return [by_id[chunk_id] for chunk_id in ordered if chunk_id in by_id]
