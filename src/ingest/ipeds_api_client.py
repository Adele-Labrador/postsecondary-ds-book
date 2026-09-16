"""Thin client for the Urban Institute Education Data Portal API.

The Urban Institute wraps IPEDS (and other NCES collections) in a
developer-friendly REST API returning JSON
(https://educationdata.urban.org/documentation/). This is a convenience
alternative to downloading and unzipping NCES's Complete Data Files by hand,
useful for readers who want a fully scripted pull with no manual download
step.

Because the endpoint schema mirrors IPEDS component variable names closely,
this client returns a DataFrame with the same standardized column names used
by ``ipeds_complete_files.load_component`` wherever a matching mapping
exists, so downstream feature/model code does not need to care which
ingestion path produced the data.
"""

from __future__ import annotations

import pandas as pd
import requests

BASE_URL = "https://educationdata.urban.org/api/v1"

# Endpoint templates keyed by the same component names used in
# ipeds_complete_files.COMPONENT_FILE_PREFIX, so callers can request either
# ingestion path with one component vocabulary.
ENDPOINTS = {
    "institutional_characteristics": "/college-university/ipeds/directory/{year}/",
    "fall_enrollment": "/college-university/ipeds/fall-enrollment/{year}/",
    "admissions": "/college-university/ipeds/admissions-enrollment/{year}/",
    "graduation_rates": "/college-university/ipeds/grad-rates/{year}/",
    "student_financial_aid": "/college-university/ipeds/finance/{year}/",
}

_API_TO_STANDARD = {
    "unitid": "unitid",
    "inst_name": "institution_name",
    "sector": "sector",
    "control": "control",
    "level": "level",
    "state_abbr": "state",
}


def fetch_endpoint(
    component: str, year: int, session: requests.Session | None = None, params: dict | None = None
) -> pd.DataFrame:
    """Fetch one page (or the full result, if the API is not paginated for
    this endpoint) of a component/year combination and return a DataFrame
    with standardized column names.
    """
    if component not in ENDPOINTS:
        raise KeyError(
            f"No Education Data Portal endpoint configured for '{component}'. "
            f"Known components: {sorted(ENDPOINTS)}"
        )

    url = BASE_URL + ENDPOINTS[component].format(year=year)
    http = session or requests
    response = http.get(url, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("results", payload) if isinstance(payload, dict) else payload

    df = pd.json_normalize(records)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={k: v for k, v in _API_TO_STANDARD.items() if k in df.columns})
    df["survey_year"] = year
    if "unitid" in df.columns:
        df["unitid"] = df["unitid"].astype(int)
    return df


def parse_payload(component: str, year: int, payload) -> pd.DataFrame:
    """Pure parsing path used by tests: takes an already-fetched JSON
    payload (as returned by ``response.json()``, either a dict with a
    ``results`` key or a bare list of records) instead of making a network
    call, so the standardization logic can be unit tested offline.
    """
    records = payload.get("results", payload) if isinstance(payload, dict) else payload
    df = pd.json_normalize(records)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={k: v for k, v in _API_TO_STANDARD.items() if k in df.columns})
    df["survey_year"] = year
    if "unitid" in df.columns:
        df["unitid"] = df["unitid"].astype(int)
    return df
