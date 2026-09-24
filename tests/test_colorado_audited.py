"""Tests for the audited CU/CSU finance layer (FY 2023-24 and FY 2024-25)."""

import json
from pathlib import Path

import pytest

from src.ingest import colorado_audited as ca

BUILT = Path("dashboard/data/colorado_audited.json")


def w(text, x0, top, width=None):
    """A pdfplumber-style word."""
    return {"text": text, "x0": x0, "x1": x0 + (width or 6 * len(text)), "top": top}


def test_parse_amount_handles_statement_styles():
    assert ca.parse_amount("1,234.50") == 1234.5
    assert ca.parse_amount("(1,234.50)") == -1234.5
    assert ca.parse_amount("-47,155") == -47155
    assert ca.parse_amount("-") == 0.0
    assert ca.parse_amount("$ 15,569") == 15569


def test_page_values_joins_fragments_and_pairs_nearest_label():
    words = [
        w("FY", 903, 50, 12),
        w("2025", 918, 50, 18),
        # Group heading on the value's line, row label a few points below.
        w("NONOPERATING", 40, 80, 50),
        w("REVENUES", 91, 80, 25),
        w("FEDERAL", 144, 87, 20),
        w("PELL", 165, 87, 12),
        w("GRANT", 178, 87, 15),
        w("1", 905, 80, 3),
        w(",834,217,932.74", 908, 80, 40),
        # A fund-column number leaking into the label area is ignored.
        w("GIFTS", 144, 100, 15),
        w("7", 330, 100, 3),
        w("(", 900, 100, 2),
        w("5,000.00)", 902, 100, 30),
        # The total line starts left of the group cutoff but is kept.
        w("TOTAL", 68, 115, 20),
        w("NONOPERATING", 90, 115, 50),
        w("-", 915, 115, 3),
    ]
    assert ca.page_values(words) == [
        ("FEDERAL PELL GRANT", 1834217932.74),
        ("GIFTS", -5000.0),
        ("TOTAL NONOPERATING", 0.0),
    ]


def test_clean_label_drops_pledged_note():
    assert ca.clean_label("STUDENT FEES, NET (PLEDGED REVENUES OF $1,234)") == "STUDENT FEES, NET"


def test_pick_first_and_last_occurrence():
    pairs = [("STUDENT TUITION, NET STUDENT TUITION", 100.0), ("STUDENT TUITION, NET", 80.0)]
    assert ca.pick(pairs, "STUDENT TUITION", "first") == 100.0
    assert ca.pick(pairs, "STUDENT TUITION, NET", "last") == 80.0
    assert ca.pick(pairs, "GIFTS", "last") is None


def test_csu_line_skips_notes_and_captions():
    lines = [
        "Auxiliary enterprises, (including $197,249 and $189,686",
        "Auxiliary enterprises 214,114 - 204,675 -",
        "State fee for service revenue (Note 23) 190,159 - 169,837 -",
    ]
    assert ca.csu_line(lines, "Auxiliary enterprises") == (214_114_000, 204_675_000)
    assert ca.csu_line(lines, "State fee for service revenue") == (190_159_000, 169_837_000)


def test_check_rejects_parts_that_do_not_sum():
    values = {k: 0.0 for k in ca.REVENUE_PARTS + ca.EXPENSE_PARTS}
    values.update(operatingRevenue=10.0, operatingExpense=0.0, tuitionFeesNet=10.0)
    assert ca.check(values, "x") is None
    values["operatingExpense"] = 1e6
    with pytest.raises(ValueError, match="expense parts"):
        ca.check(values, "x")


def test_reconcile_cu_fixes_a_single_sign_flip():
    def ent(nonop, rev=0.0):
        return {
            "nonoperating": nonop,
            "operatingRevenue": rev,
            "operatingExpense": rev,
            "operatingIncome": 0.0,
        }

    year = {
        "cub": ent(10.0),
        "uccs": ent(-5.0),
        "ucd": ent(1.0),
        "cusys": ent(0.0),
        "cu": ent(16.0),
    }
    notes = ca.reconcile_cu(year, "FY 2023-24")
    assert year["uccs"]["nonoperating"] == 5.0
    assert len(notes) == 1 and "UCCS" in notes[0]


@pytest.fixture(scope="module")
def data():
    return json.loads(BUILT.read_text())


@pytest.fixture(scope="module")
def ent(data):
    return {e["id"]: e for e in data["entities"]}


@pytest.mark.skipif(not BUILT.exists(), reason="audited layer not built")
class TestBuiltLayer:
    def test_years_and_entities(self, data, ent):
        assert data["meta"]["years"] == ["FY 2023-24", "FY 2024-25"]
        assert set(ent) == {"cub", "uccs", "ucd", "cusys", "cu", "csu"}
        assert ent["csu"]["unitids"] == [126818, 128106, 476975]
        assert ent["cusys"]["fte"] is None

    def test_pinned_cu_boulder_fy2025(self, ent):
        v = ent["cub"]["values"]
        assert v["instruction"][1] == 685_619_246
        assert v["operatingRevenue"][1] == 2_206_173_502
        assert v["tuitionFeesNet"][1] == 949_352_593
        assert v["pell"][1] == 36_369_589

    def test_pinned_csu_fy2025_and_restated_fy2024(self, ent):
        v = ent["csu"]["values"]
        assert v["instruction"] == [433_521_000, 454_804_000]
        assert v["operatingExpense"] == [1_767_507_000, 1_888_939_000]
        assert v["changeInNetPosition"] == [99_539_000, 98_912_000]
        assert v["allowance"] == [153_418_000, 174_068_000]

    def test_components_sum_to_totals(self, ent):
        for e in ent.values():
            v = e["values"]
            for i in (0, 1):
                rev = sum(v[k][i] for k in ca.REVENUE_PARTS)
                exp = sum(v[k][i] for k in ca.EXPENSE_PARTS)
                assert abs(rev - v["operatingRevenue"][i]) <= 10, e["id"]
                assert abs(exp - v["operatingExpense"][i]) <= 10, e["id"]
                assert v["operatingIncome"][i] == pytest.approx(
                    v["operatingRevenue"][i] - v["operatingExpense"][i], abs=2
                )

    def test_cu_campuses_tie_to_consolidated_nonoperating(self, ent):
        for i in (0, 1):
            parts = sum(ent[c]["values"]["nonoperating"][i] for c in ca.CU_PARTS)
            assert abs(parts - ent["cu"]["values"]["nonoperating"][i]) <= 5
            pell = sum(ent[c]["values"]["pell"][i] for c in ca.CU_PARTS)
            assert abs(pell - ent["cu"]["values"]["pell"][i]) <= 5
