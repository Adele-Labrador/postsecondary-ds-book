"""Checks on dashboard/data/colorado_formula.json, the formula lab's input.

The file is written by the appendix of notebook 11. These tests re-run the Step 2
arithmetic on the exported window series, independently of the notebook, and
confirm they reproduce the notebook's FY2025-26 reconstruction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "dashboard" / "data" / "colorado_formula.json"


@pytest.fixture(scope="module")
def lab() -> dict:
    return json.loads(PATH.read_text())


def d_ratio(v: list[float]) -> float:
    return (sum(v) / 4) / (sum(v[:3]) / 3)


def shares(lab: dict, retention: str = "ft") -> dict[str, float]:
    boards = lab["boards"]
    base = sum(b["base"] for b in boards)
    prior = {b["id"]: b["base"] / base for b in boards}
    out = dict.fromkeys(prior, 0.0)
    for metric, weight in lab["weights"].items():
        if metric == "first_gen":
            d = dict.fromkeys(prior, 1.0)
        elif metric == "retention" and retention == "incl":
            d = {b["id"]: d_ratio(b["retentionInclusive"]) for b in boards}
        else:
            d = {b["id"]: d_ratio(b["series"][metric]) for b in boards}
        adj = {k: prior[k] * d[k] for k in prior}
        total = sum(adj.values())
        for k in out:
            out[k] += weight * adj[k] / total
    return out


def test_schema(lab):
    assert len(lab["boards"]) == 10
    assert abs(sum(lab["weights"].values()) - 1) < 1e-12
    for b in lab["boards"]:
        assert set(b["series"]) == set(lab["weights"]) - {"first_gen"}
        assert all(len(v) == 4 and None not in v for v in b["series"].values())
        assert len(b["retentionInclusive"]) == 4


def test_reconstruction_matches_notebook(lab):
    s = shares(lab)
    pot = sum(b["actual"] for b in lab["boards"])
    for b in lab["boards"]:
        pct = (s[b["id"]] * pot / b["base"] - 1) * 100
        assert pct == pytest.approx(b["notebookPct"], abs=1e-3), b["id"]


def test_part_time_reallocation_is_small(lab):
    # Notebook 11 section 10b: recomputed inclusive retention moves about $58,741.
    a, b = shares(lab), shares(lab, "incl")
    moved = sum(max(b[k] - a[k], 0) for k in a) * lab["meta"]["fiscalNoteBase"]
    assert moved == pytest.approx(58_741, rel=0.01)


def test_cccs_sensitivity_never_reaches_fiscal_note(lab):
    note = next(b for b in lab["boards"] if b["id"] == "CCCS")["fiscalNote"]["part_time"]
    effects = [r["CCCS part-time effect ($)"] for r in lab["cccs"]["sensitivity"]]
    assert max(effects) < note
    assert min(effects) < 0 < max(effects)
    assert lab["cccs"]["visibleSharePt"] < 0.15


def test_coverage_units(lab):
    cccs = [u for u in lab["units"] if u["board"] == "CCCS"]
    assert len(cccs) == 13
    used = {u["unitid"] for u in cccs if u["status"]["retention_all"] == "used"}
    assert used == set(lab["cccs"]["visible"])
