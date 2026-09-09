"""Parsing tests. These read recorded fixtures and never touch the network."""

import json
from pathlib import Path

import pytest

from ingestion.clinicaltrials import normalize_study
from ingestion.pubmed import parse_articles

FIXTURES = Path(__file__).parent / "fixtures"

REQUIRED_KEYS = {"source", "document_id", "title", "text", "metadata"}


@pytest.fixture(scope="module")
def study():
    raw = json.loads((FIXTURES / "clinicaltrials_sample.json").read_text())
    return normalize_study(raw["studies"][0])


@pytest.fixture(scope="module")
def article():
    xml = (FIXTURES / "pubmed_sample.xml").read_text()
    return parse_articles(xml)[0]


def test_study_has_the_common_document_shape(study):
    assert REQUIRED_KEYS <= set(study)
    assert study["source"] == "clinicaltrials"


def test_study_id_is_the_nct_number(study):
    assert study["document_id"].startswith("NCT")


def test_study_text_includes_title_and_condition(study):
    assert study["title"] in study["text"]
    assert "Obesity" in study["text"]


def test_study_metadata_values_are_all_scalars(study):
    # ChromaDB rejects list values, so lists must be flattened at ingestion time.
    for key, value in study["metadata"].items():
        assert isinstance(value, (str, int, float, bool)), f"{key} is {type(value)}"


def test_study_url_points_at_clinicaltrials(study):
    assert study["metadata"]["url"] == f"https://clinicaltrials.gov/study/{study['document_id']}"


def test_article_has_the_common_document_shape(article):
    assert REQUIRED_KEYS <= set(article)
    assert article["source"] == "pubmed"


def test_article_id_is_a_numeric_pmid(article):
    assert article["document_id"].isdigit()


def test_article_text_includes_the_abstract(article):
    assert len(article["text"]) > 200
    assert article["title"] in article["text"]


def test_article_metadata_carries_journal_and_date(article):
    assert article["metadata"]["journal"]
    assert article["metadata"]["date"].startswith("20")


def test_article_metadata_values_are_all_scalars(article):
    for key, value in article["metadata"].items():
        assert isinstance(value, (str, int, float, bool)), f"{key} is {type(value)}"


def test_parse_articles_returns_every_article_in_the_file():
    xml = (FIXTURES / "pubmed_sample.xml").read_text()
    assert len(parse_articles(xml)) == 3


def test_both_sources_agree_on_the_document_shape(study, article):
    assert set(study) == set(article)


def test_article_date_uses_numeric_months(article):
    # PubMed writes "2026-Sep"; both sources must agree on YYYY-MM-DD.
    parts = article["metadata"]["date"].split("-")
    assert all(p.isdigit() for p in parts), article["metadata"]["date"]
