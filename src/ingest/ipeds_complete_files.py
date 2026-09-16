"""Load and standardize one IPEDS survey component for one year.

Source: NCES IPEDS Complete Data Files, distributed as zipped CSV files by
survey component and year (https://nces.ed.gov/ipeds/use-the-data). This
module assumes the ZIP has already been downloaded and extracted into
``data/raw/<component>/<year>.csv`` (see :func:`download_component` for a
thin wrapper around the download step).

Column names below follow IPEDS's documented variable-naming conventions
(see the book's variable-to-task reference table), but NCES occasionally
renames variables between release years -- always confirm against that
year's IPEDS data dictionary before pointing this at a new release.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests

# Maps a friendly component name to (a) the IPEDS file prefix used in
# Complete Data Files downloads and (b) the rename map from raw column
# names to the standardized names used throughout src/features and
# src/models.
COMPONENT_FILE_PREFIX = {
    "institutional_characteristics": "IC",
    "fall_enrollment": "EF",
    "human_resources": "HR",
    "finance": "F",
    "student_financial_aid": "SFA",
    "completions": "C",
    "graduation_rates": "GR",
    "outcome_measures": "OM",
    "admissions": "ADM",
}

RENAME_MAPS = {
    "institutional_characteristics": {
        "unitid": "unitid",
        "instnm": "institution_name",
        "control": "control",
        "iclevel": "level",
        "sector": "sector",
        "stabbr": "state",
    },
    "fall_enrollment": {
        "unitid": "unitid",
        "eftotlt": "total_enrollment",
        "eftotlm": "total_enrollment_men",
        "eftotlw": "total_enrollment_women",
        "ft_students": "ft_students",
        "pt_students": "pt_students",
    },
    "human_resources": {
        "unitid": "unitid",
        "hrtotlt": "total_staff",
        "fte_instructional_faculty": "fte_instructional_faculty",
    },
    "finance": {
        "unitid": "unitid",
        "f1b01": "total_revenue",
        "f1b02": "tuition_revenue",
        "f1b03": "govt_appropriations",
        "f1b04": "total_expenses",
    },
    "student_financial_aid": {
        "unitid": "unitid",
        "scfa2": "total_undergrad",
        "pgrnt_n": "pell_recipients",
        "fgrnt_n": "federal_grant_recipients",
        "total_grant_aid": "total_grant_aid",
        "aid_recipients": "aid_recipients",
    },
    "completions": {
        "unitid": "unitid",
        "cipcode": "cip_code",
        "ctotalt": "credentials_awarded",
        "awlevel": "credential_level",
    },
    "graduation_rates": {
        "unitid": "unitid",
        "grtotlt": "cohort_size",
        "grtotlm": "completers_150pct",
    },
    "outcome_measures": {
        "unitid": "unitid",
        "omenrap": "pell_completers_share",
        "omenrup": "non_pell_completers_share",
    },
    "admissions": {
        "unitid": "unitid",
        "applcn": "applicants",
        "admssn": "admits",
        "enrlt": "enrolled",
    },
}


def raw_file_path(component: str, year: int, raw_dir: str = "data/raw") -> Path:
    prefix = COMPONENT_FILE_PREFIX[component]
    return Path(raw_dir) / component / f"{prefix}{year}.csv"


def download_component(
    component: str,
    year: int,
    url: str,
    raw_dir: str = "data/raw",
    session: requests.Session | None = None,
) -> Path:
    """Download a single Complete Data Files CSV for one component/year.

    ``url`` should point directly at the CSV (or an already-unzipped file
    served over HTTP) -- NCES's Complete Data Files are distributed as ZIPs,
    so a real pipeline would unzip before calling this. Kept as a thin,
    mockable function so ingestion logic can be tested without network
    access (see tests/test_ingest_complete_files.py).
    """
    dest = raw_file_path(component, year, raw_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    http = session or requests
    response = http.get(url, timeout=60)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return dest


def load_component(
    component: str, year: int, raw_dir: str = "data/raw", path: str | os.PathLike | None = None
) -> pd.DataFrame:
    """Read one standardized survey-component table for one year.

    Parameters
    ----------
    component:
        Key into ``COMPONENT_FILE_PREFIX`` / ``RENAME_MAPS``.
    year:
        Survey year (used to locate the default file path and stamped onto
        the ``survey_year`` column).
    raw_dir:
        Base directory holding raw downloads, ignored if ``path`` is given.
    path:
        Optional explicit CSV path, mainly used by tests to point at a
        small fixture file instead of a full-size download.
    """
    if component not in RENAME_MAPS:
        raise KeyError(
            f"Unknown IPEDS component '{component}'. " f"Known components: {sorted(RENAME_MAPS)}"
        )

    csv_path = Path(path) if path is not None else raw_file_path(component, year, raw_dir)
    df = pd.read_csv(csv_path, encoding="latin1")
    df.columns = [c.strip().lower() for c in df.columns]

    rename_map = {k: v for k, v in RENAME_MAPS[component].items() if k in df.columns}
    df = df.rename(columns=rename_map)

    df["survey_year"] = year
    df["unitid"] = df["unitid"].astype(int)

    # Keep only columns we know how to standardize, plus the join keys.
    keep_cols = ["unitid", "survey_year"] + [c for c in rename_map.values() if c != "unitid"]
    keep_cols = [c for c in keep_cols if c in df.columns]
    return df[keep_cols]
