"""Retriever tests use a fake embedding function, so they need no model download."""

import hashlib

import numpy as np
import pytest
from chromadb.api.types import EmbeddingFunction

from retrieval.vector_store import HybridRetriever, reciprocal_rank_fusion


class FakeEmbedding(EmbeddingFunction):
    """Deterministic bag-of-words vectors. Shared words means similar vectors."""

    def __init__(self):
        pass

    def __call__(self, input):
        vectors = []
        for text in input:
            vector = np.zeros(64, dtype=np.float32)
            for word in text.lower().split():
                index = int(hashlib.md5(word.encode()).hexdigest(), 16) % 64
                vector[index] += 1.0
            norm = np.linalg.norm(vector)
            vectors.append((vector / norm if norm else vector).tolist())
        return vectors

    @staticmethod
    def name():
        return "fake"

    def embed_query(self, input):
        return self(input)

    @staticmethod
    def build_from_config(config):
        return FakeEmbedding()

    def get_config(self):
        return {}


def _chunk(chunk_id, text, **metadata):
    base = {"source": "pubmed", "document_id": chunk_id.split(":")[1], "chunk_index": 0}
    return {"chunk_id": chunk_id, "text": text, "metadata": {**base, **metadata}}


CHUNKS = [
    _chunk("pubmed:1:0", "semaglutide reduced body weight in adults with obesity",
           condition="Obesity"),
    _chunk("pubmed:2:0", "patients demonstrated significant weight loss outcomes",
           condition="Obesity"),
    _chunk("pubmed:3:0", "inhaled corticosteroids for asthma control in children",
           condition="Asthma", source="clinicaltrials"),
    _chunk("pubmed:4:0", "blood pressure lowering therapy after myocardial infarction",
           condition="Hypertension"),
]


@pytest.fixture
def retriever(tmp_path):
    store = HybridRetriever(persist_dir=tmp_path / "chroma", embedding_fn=FakeEmbedding())
    store.add_chunks(CHUNKS)
    return store


def test_rrf_ranks_a_document_that_places_well_in_both_lists_first():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "a", "d"]])
    assert fused[0] == "a"


def test_rrf_includes_documents_found_by_only_one_list():
    fused = reciprocal_rank_fusion([["a", "b"], ["c"]])
    assert set(fused) == {"a", "b", "c"}


def test_rrf_handles_empty_lists():
    assert reciprocal_rank_fusion([[], []]) == []


def test_add_chunks_stores_every_chunk(retriever):
    assert retriever.count() == len(CHUNKS)


def test_adding_the_same_chunks_again_does_not_duplicate(retriever):
    retriever.add_chunks(CHUNKS)
    assert retriever.count() == len(CHUNKS)


def test_keyword_search_finds_an_exact_drug_name(retriever):
    # Dense search alone tends to miss rare tokens; BM25 is why this works.
    results = retriever.search("semaglutide", k=2)
    assert results[0]["metadata"]["document_id"] == "1"


def test_search_returns_chunks_with_text_and_metadata(retriever):
    result = retriever.search("weight loss", k=1)[0]
    assert result["text"]
    assert result["metadata"]["condition"]
    assert result["chunk_id"]


def test_search_respects_k(retriever):
    assert len(retriever.search("weight", k=2)) == 2


def test_metadata_filter_restricts_results(retriever):
    results = retriever.search("treatment", k=10, filters={"condition": "Asthma"})
    assert results
    assert all(r["metadata"]["condition"] == "Asthma" for r in results)


def test_filter_on_source_restricts_results(retriever):
    results = retriever.search("treatment", k=10, filters={"source": "clinicaltrials"})
    assert all(r["metadata"]["source"] == "clinicaltrials" for r in results)


def test_search_on_an_empty_store_returns_nothing(tmp_path):
    store = HybridRetriever(persist_dir=tmp_path / "empty", embedding_fn=FakeEmbedding())
    assert store.search("anything") == []


def test_the_store_reopens_from_disk(tmp_path):
    first = HybridRetriever(persist_dir=tmp_path / "chroma", embedding_fn=FakeEmbedding())
    first.add_chunks(CHUNKS)
    second = HybridRetriever(persist_dir=tmp_path / "chroma", embedding_fn=FakeEmbedding())
    assert second.count() == len(CHUNKS)
    assert second.search("semaglutide", k=1)[0]["metadata"]["document_id"] == "1"
