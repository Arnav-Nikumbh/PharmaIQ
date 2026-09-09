import json

import pytest

from ingestion import ingest


@pytest.fixture
def fake_source(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest.config, "RAW_DIR", tmp_path)
    calls = []

    def fake_fetch(topic, limit):
        calls.append(topic)
        return [{
            "source": "pubmed", "document_id": "1", "title": "T",
            "text": "body text", "metadata": {"source": "pubmed", "document_id": "1"},
        }]

    monkeypatch.setitem(ingest.FETCHERS, "pubmed", fake_fetch)
    return calls


def test_slugify_makes_a_safe_filename():
    assert ingest.slugify("GLP-1 obesity / weight!") == "glp-1-obesity-weight"


def test_collect_writes_a_cache_file(fake_source, tmp_path):
    ingest.collect("some topic", 5, ["pubmed"])
    cached = json.loads((tmp_path / "pubmed_some-topic.json").read_text())
    assert cached[0]["document_id"] == "1"


def test_collect_reuses_the_cache_instead_of_refetching(fake_source):
    ingest.collect("some topic", 5, ["pubmed"])
    ingest.collect("some topic", 5, ["pubmed"])
    assert len(fake_source) == 1


def test_refresh_forces_a_new_fetch(fake_source):
    ingest.collect("some topic", 5, ["pubmed"])
    ingest.collect("some topic", 5, ["pubmed"], refresh=True)
    assert len(fake_source) == 2
