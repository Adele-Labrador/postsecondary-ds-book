"""Checks on dashboard/data/colorado_formula.json, the formula lab's input.

The file is written by the appendix of notebook 11. These tests re-run the Step 2
arithmetic on the exported window series, independently of the notebook, and
confirm they reproduce the notebook's FY2025-26 reconstruction and its FY2026-27
test against the request.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "dashboard" / "data" / "colorado_formula.json"


@pytest.fixture(scope="module")
def lab() -> dict:
    return json.loads(PATH.read_text())


def year(lab: dict, label: str) -> dict:
    return next(y for y in lab["years"] if y["fiscalYear"] == label)


def d_ratio(v: list[float]) -> float:
    return (sum(v) / 4) / (sum(v[:3]) / 3)


def shares(lab: dict, label: str, retention: str = "ft") -> dict[str, float]:
    boards = year(lab, label)["boards"]
    base = sum(b["base"] for b in boards.values())
    prior = {k: b["base"] / base for k, b in boards.items()}
    out = dict.fromkeys(prior, 0.0)
    for metric, weight in lab["weights"].items():
        if metric == "first_gen":
            d = dict.fromkeys(prior, 1.0)
        elif metric == "retention" and retention == "incl":
            d = {k: d_ratio(b["retentionInclusive"]) for k, b in boards.items()}
        else:
            d = {k: d_ratio(b["series"][metric]) for k, b in boards.items()}
        adj = {k: prior[k] * d[k] for k in prior}
        total = sum(adj.values())
        for k in out:
            out[k] += weight * adj[k] / total
    return out


def corr(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    return sab / (saa * sbb) ** 0.5


def test_schema(lab):
    assert len(lab["boards"]) == 10
    assert abs(sum(lab["weights"].values()) - 1) < 1e-12
    assert [y["fiscalYear"] for y in lab["years"]] == ["FY 2025-26", "FY 2026-27"]
    assert [y["target"] for y in lab["years"]] == ["actual", "request"]
    for y in lab["years"]:
        assert set(y["boards"]) == {b["id"] for b in lab["boards"]}
        assert len(y["status"]) == len(lab["units"]) == 25
        for b in y["boards"].values():
            assert set(b["series"]) == set(lab["weights"]) - {"first_gen"}
            assert all(len(v) == 4 and None not in v for v in b["series"].values())
            assert len(b["retentionInclusive"]) == 4
    for u in lab["units"]:
        assert len(u["ftCohort"]) == len(lab["meta"]["cohortYears"])


@pytest.mark.parametrize("label", ["FY 2025-26", "FY 2026-27"])
def test_reconstruction_matches_notebook(lab, label):
    s = shares(lab, label)
    boards = year(lab, label)["boards"]
    pot = sum(b["target"] for b in boards.values())
    for k, b in boards.items():
        pct = (s[k] * pot / b["base"] - 1) * 100
        assert pct == pytest.approx(b["notebookPct"], abs=1e-3), (label, k)


def test_fy2026_27_tracks_request(lab):
    # Notebook 11 section 7: rebuilt reallocation correlates 0.63 with the request.
    y = year(lab, "FY 2026-27")
    s = shares(lab, "FY 2026-27")
    pot = sum(b["base"] for b in y["boards"].values())
    rebuilt = [s[k] * pot - b["base"] for k, b in y["boards"].items()]
    request = [b["target"] - b["base"] for b in y["boards"].values()]
    assert abs(sum(request)) < 5  # Step 2 adjustments net to zero in the request
    assert corr(rebuilt, request) == pytest.approx(0.63, abs=0.01)
    assert y["lagged"] == ["pell_share"]


def test_part_time_reallocation_is_small(lab):
    # Notebook 11 section 10b: recomputed inclusive retention moves about $58,706.
    a, b = shares(lab, "FY 2025-26"), shares(lab, "FY 2025-26", "incl")
    moved = sum(max(b[k] - a[k], 0) for k in a) * lab["meta"]["fiscalNoteBase"]
    assert moved == pytest.approx(58_706, rel=0.01)


def test_cccs_sensitivity_never_reaches_fiscal_note(lab):
    note = next(b for b in lab["boards"] if b["id"] == "CCCS")["fiscalNote"]["part_time"]
    effects = [r["CCCS part-time effect ($)"] for r in lab["cccs"]["sensitivity"]]
    assert max(effects) < note
    assert min(effects) < 0 < max(effects)
    assert lab["cccs"]["visibleSharePt"] < 0.15


def test_coverage_units(lab):
    cccs = {u["unitid"] for u in lab["units"] if u["board"] == "CCCS"}
    assert len(cccs) == 13
    status = year(lab, "FY 2025-26")["status"]
    used = {u for u in cccs if status[str(u)]["retention_all"] == "used"}
    assert used == set(lab["cccs"]["visible"])
    # Colorado Northwestern reports no full-time cohort for fall 2023, so FY2026-27 keeps five.
    later = year(lab, "FY 2026-27")["status"]
    assert sum(later[str(u)]["retention"] == "used" for u in cccs) == 5
