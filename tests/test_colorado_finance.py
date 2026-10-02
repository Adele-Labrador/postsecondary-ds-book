"""Tests for the Colorado campus finance builder (IPEDS F1A + EFIA)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.ingest import colorado_finance as cf

BUILT = Path("dashboard/data/colorado_finance.json")


def test_stems_and_labels():
    assert cf.finance_stem(2014) == "F1415_F1A"
    assert cf.finance_stem(2023) == "F2324_F1A"
    assert cf.finance_stem(2099) == "F9900_F1A"
    assert cf.fiscal_label(2023) == "FY 2023-24"


def test_semiannual_cpi_pairs_second_half_with_next_first_half():
    lines = [
        "CUUSS48BSA0\t2014\tS01\t235.736",
        "CUUSS48BSA0\t2014\tS02\t238.664",
        "CUUSS48BSA0\t2014\tS03\t237.200",  # annual average: ignored
        "CUUSS48BSA0\t2015\tS01\t238.086",
        "CUUSS48BSA0\t2015\tS02\t241.895",  # no 2016 S01 yet: no FY 2015-16
        "CUURS48BSA0\t2015\tM01\t999.0",  # other series: ignored
    ]
    assert cf.semiannual_fiscal_cpi(lines) == {"FY 2014-15": 238.375}


def test_discount_rate():
    assert cf.discount_rate(750, 250) == 0.25
    assert cf.discount_rate(None, 10) is None
    assert cf.discount_rate(0, 0) is None


def test_measure_sums_codes_and_keeps_missing_as_none():
    frame = pd.DataFrame(
        {"A": [1.4, None], "B": [2.0, None], "C": ["3", None]}, index=pd.Index([10, 20])
    )
    assert cf.measure(frame, 10, ("A", "B", "C")) == 6
    assert cf.measure(frame, 20, ("A", "B")) is None
    assert cf.measure(frame, 30, ("A",)) is None


def test_check_totals_rejects_inconsistent_revenue():
    ok = pd.DataFrame({"F1B09": [60], "F1B19": [40], "F1B27": [100]}, index=[1])
    cf.check_totals(ok, 1)
    bad = pd.DataFrame({"F1B09": [60], "F1B19": [40], "F1B27": [150]}, index=[1])
    with pytest.raises(ValueError):
        cf.check_totals(bad, 1)


def test_units_collapse_campuses_sharing_a_unitid():
    units = {u["unitid"]: u for u in cf.units()}
    assert len(units) == 27
    assert units[126562]["name"] == "CU Denver | Anschutz"
    assert len(units[126562]["campuses"]) == 2
    assert len(units[126818]["campuses"]) == 2  # Fort Collins + vet med
    assert units[127200]["board"] == "CCCS"


@pytest.mark.skipif(not BUILT.exists(), reason="built file not present")
def test_built_file_structure_and_reference_values():
    data = json.loads(BUILT.read_text())
    meta = data["meta"]
    assert meta["years"][0] == "FY 2014-15" and meta["years"][-1] == "FY 2023-24"
    assert meta["deflator"][-1] == 1.0
    assert all(a > b for a, b in zip(meta["deflator"], meta["deflator"][1:]))
    units = {u["unitid"]: u for u in data["units"]}
    assert len(units) == 27
    for u in units.values():
        for key in ("tuition", "instruction", "instructionSalaries", "fte", "totalRevenue"):
            assert len(u[key]) == 10 and all(v is not None for v in u[key]), (u["name"], key)

    boulder = units[126614]
    # EFIA2024 FTEUG 31,778 + FTEGD 4,927 = 36,705.
    assert boulder["fte"][-1] == 36_705
    assert boulder["totalRevenue"][-1] == 2_219_041_113
    assert boulder["tuition"][-1] == 888_091_469
    assert boulder["discountRate"][-1] == pytest.approx(0.1564)
    # Local district colleges are funded by district property taxes.
    assert units[126207]["local"][-1] == 132_752_239
    # Colorado routes state money through contracts, not appropriations.
    assert boulder["state"][-1] < boulder["tuition"][-1] / 5
