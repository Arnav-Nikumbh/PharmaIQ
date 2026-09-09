"""Fetch and normalize studies from ClinicalTrials.gov.

The public API v2 needs no key. Every study becomes the same document shape
that the PubMed fetcher produces, so the rest of the pipeline does not care
which source a document came from.
"""

import requests

API_URL = "https://clinicaltrials.gov/api/v2/studies"
PAGE_SIZE = 50
TIMEOUT = 30


def _join(values: list[str] | None) -> str:
    return ", ".join(v for v in (values or []) if v)


def normalize_study(study: dict) -> dict:
    """Turn one API study into the common document shape."""
    section = study.get("protocolSection", {})
    ident = section.get("identificationModule", {})
    conditions = section.get("conditionsModule", {}).get("conditions", [])
    interventions = [
        i.get("name", "")
        for i in section.get("armsInterventionsModule", {}).get("interventions", [])
    ]
    description = section.get("descriptionModule", {})
    design = section.get("designModule", {})
    status = section.get("statusModule", {})
    outcomes = [
        f"{o.get('measure', '')}: {o.get('description', '')}".strip(": ")
        for o in section.get("outcomesModule", {}).get("primaryOutcomes", [])
    ]

    nct_id = ident.get("nctId", "")
    title = ident.get("briefTitle") or ident.get("officialTitle") or nct_id

    parts = [
        title,
        f"Conditions: {_join(conditions)}" if conditions else "",
        f"Interventions: {_join(interventions)}" if interventions else "",
        description.get("briefSummary", ""),
        f"Primary outcomes: {' | '.join(outcomes)}" if outcomes else "",
        section.get("eligibilityModule", {}).get("eligibilityCriteria", ""),
    ]

    return {
        "source": "clinicaltrials",
        "document_id": nct_id,
        "title": title,
        "text": "\n\n".join(p for p in parts if p),
        "metadata": {
            "source": "clinicaltrials",
            "document_id": nct_id,
            "title": title,
            "condition": _join(conditions),
            "intervention": _join(interventions),
            "study_type": design.get("studyType", ""),
            "phase": _join(design.get("phases")),
            "status": status.get("overallStatus", ""),
            "date": status.get("startDateStruct", {}).get("date", ""),
            "url": f"https://clinicaltrials.gov/study/{nct_id}",
        },
    }


def fetch_studies(topic: str, limit: int = 25) -> list[dict]:
    """Search ClinicalTrials.gov and return up to `limit` normalized documents."""
    documents: list[dict] = []
    page_token = None
    while len(documents) < limit:
        params = {
            "query.term": topic,
            "pageSize": min(PAGE_SIZE, limit - len(documents)),
            "fields": "protocolSection",
        }
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(API_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        studies = payload.get("studies", [])
        if not studies:
            break
        documents.extend(normalize_study(s) for s in studies)
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return documents[:limit]
