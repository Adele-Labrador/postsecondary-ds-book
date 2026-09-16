"""Shared pytest fixtures: put ``src`` on the import path and load the small
synthetic IPEDS-style fixture files used across the test suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def ic_raw_path() -> Path:
    return FIXTURES / "ic_2022.csv"


@pytest.fixture
def ef_raw_path() -> Path:
    return FIXTURES / "ef_2022.csv"


@pytest.fixture
def hr_raw_path() -> Path:
    return FIXTURES / "hr_2022.csv"


@pytest.fixture
def sfa_raw_path() -> Path:
    return FIXTURES / "sfa_2022.csv"


@pytest.fixture
def carnegie_df() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "carnegie.csv")


@pytest.fixture
def crosswalk_df() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "crosswalk.csv")
