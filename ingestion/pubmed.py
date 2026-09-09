"""Fetch and normalize articles from PubMed via NCBI E-utilities.

No API key is required. Without one NCBI allows about three requests per
second, so the fetcher sleeps briefly between calls.
"""

import time
import xml.etree.ElementTree as ET

import requests

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BATCH_SIZE = 50
TIMEOUT = 30
POLITE_DELAY = 0.4


def _text(element, path: str) -> str:
    """Return all text under the first match of `path`, including nested tags."""
    node = element.find(path)
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def _abstract(article) -> str:
    """Join the abstract's sections, keeping their labels when present."""
    parts = []
    for node in article.findall(".//Abstract/AbstractText"):
        body = "".join(node.itertext()).strip()
        if not body:
            continue
        label = node.get("Label")
        parts.append(f"{label}: {body}" if label else body)
    return "\n\n".join(parts)


_MONTHS = {m: f"{i + 1:02d}" for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _publication_date(article) -> str:
    """Return YYYY-MM-DD, or as much of it as PubMed supplies.

    PubMed writes months as names ("Sep"). ClinicalTrials.gov writes numbers.
    Both sources are normalized to numbers here so dates stay comparable.
    """
    pub_date = article.find(".//Journal/JournalIssue/PubDate")
    if pub_date is None:
        return ""
    year = pub_date.findtext("Year", "")
    if not year:
        return pub_date.findtext("MedlineDate", "")
    parts = [year]
    month = pub_date.findtext("Month", "")
    if month:
        parts.append(_MONTHS.get(month[:3], month.zfill(2)))
        day = pub_date.findtext("Day", "")
        if day:
            parts.append(day.zfill(2))
    return "-".join(parts)


def normalize_article(article) -> dict:
    """Turn one PubmedArticle element into the common document shape."""
    pmid = _text(article, ".//MedlineCitation/PMID")
    title = _text(article, ".//Article/ArticleTitle")
    abstract = _abstract(article)
    authors = [
        f"{a.findtext('ForeName', '')} {a.findtext('LastName', '')}".strip()
        for a in article.findall(".//AuthorList/Author")
    ]
    keywords = [k.text.strip() for k in article.findall(".//KeywordList/Keyword") if k.text]

    return {
        "source": "pubmed",
        "document_id": pmid,
        "title": title,
        "text": "\n\n".join(p for p in (title, abstract) if p),
        "metadata": {
            "source": "pubmed",
            "document_id": pmid,
            "title": title,
            "journal": _text(article, ".//Journal/Title"),
            "authors": ", ".join(authors[:5]),
            "keywords": ", ".join(keywords),
            "date": _publication_date(article),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        },
    }


def parse_articles(xml_text: str) -> list[dict]:
    """Parse an efetch XML response into normalized documents."""
    root = ET.fromstring(xml_text)
    return [normalize_article(a) for a in root.findall(".//PubmedArticle")]


def fetch_articles(topic: str, limit: int = 25) -> list[dict]:
    """Search PubMed and return up to `limit` normalized documents."""
    search = requests.get(
        f"{BASE_URL}/esearch.fcgi",
        params={"db": "pubmed", "term": topic, "retmax": limit, "retmode": "json"},
        timeout=TIMEOUT,
    )
    search.raise_for_status()
    ids = search.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    documents: list[dict] = []
    for start in range(0, len(ids), BATCH_SIZE):
        time.sleep(POLITE_DELAY)
        batch = ids[start:start + BATCH_SIZE]
        fetch = requests.get(
            f"{BASE_URL}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(batch), "retmode": "xml"},
            timeout=TIMEOUT,
        )
        fetch.raise_for_status()
        documents.extend(parse_articles(fetch.text))
    return documents[:limit]
