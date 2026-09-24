"""Offline tests for the Colorado FTE and funding parsers."""

import json
from pathlib import Path

import pytest

from src.ingest import colorado

FTE_TEXT = """The Colorado Department of Higher Education
Resident Undergraduate Student FTE
FY 2019-20 FY 2020-21 FY 2021-22
Regents of the University of Colorado: 16,650 16,681 16,033
University of Colorado-Boulder 1 6,096 16,181 15,544
University of Colorado Denver - Anschutz Medical Campus 5 54 500 489
Trustees of Fort Lewis College:
Fort Lewis College 1,292 1,256 1,212
Community Colleges of Colorado: 990 932 865
Trinidad State Junior College 990 932 865
Public Summary 18,932 18,869 18,110
"""


def test_parse_fte_text_rejoins_split_leading_digit():
    years, rows, summaries = colorado.parse_fte_text(FTE_TEXT)
    assert years == ["FY 2019-20", "FY 2020-21", "FY 2021-22"]
    assert rows["University of Colorado-Boulder"] == [16096, 16181, 15544]
    assert rows["University of Colorado Denver - Anschutz Medical Campus"] == [554, 500, 489]
    assert "Regents of the University of Colorado" in summaries  # board header, not a row
    assert "Trustees of Fort Lewis College" not in rows  # header without numbers
    colorado.check_summaries(rows, summaries, "fixture")


def test_check_summaries_tolerates_rounding_but_not_parse_errors():
    rows = {"A": [100, 200], "B": [51, 49]}
    colorado.check_summaries(rows, {"Public Summary": [152, 250]}, "ok")  # off by 1
    with pytest.raises(ValueError):
        colorado.check_summaries(rows, {"Public Summary": [1510, 250]}, "bad")


@pytest.mark.parametrize(
    "label, board, unitid",
    [
        ("Western State Colorado University", "WCU", 128391),
        ("Western Colorado University", "WCU", 128391),
        ("Otero Junior College", "CCCS", 127778),
        ("Pikes Peak Community College", "CCCS", 127820),
        ("Trinidad State College", "CCCS", 128258),
        ("Colorado State University - Professional Veterinary Medicine", "CSU", 126818),
        ("University of Colorado Denver - Anschutz Medical Campus", "CU", 126562),
    ],
)
def test_renamed_institutions_map_to_one_record(label, board, unitid):
    _, got_board, got_unitid = colorado.canonical_institution(label)
    assert (got_board, got_unitid) == (board, unitid)


def test_unknown_institution_is_not_silently_mapped():
    assert colorado.canonical_institution("Colorado Christian University") is None


JBC_TEXT = """GENERAL FUND APPROPRIATIONS
Adams State University $99,999,999 $1
TABLE 1: R1 INCREASE FOR PUBLIC HIGHER EDUCATION
Adams State University $21,009,471 $22,559,678 $1,550,207 7.4%
Colorado Mesa
University 40,143,534 43,056,212 2,912,678 7.3%
Metropolitan State University 82,497,655 89,654,071 7,156,416 8.7%
CO State U. System 202,360,491 215,018,693 12,658,202 6.3%
U. of Colorado System 275,755,786 293,210,048 17,454,262 6.3%
Colorado Mountain College 10,831,151 11,562,751 731,600 6.8%
Area Technical Colleges 18,392,334 19,642,162 1,249,828 6.8%
Community College System 189,865,735 (110,122,127)
"""


def test_parse_board_rows_uses_marker_wrapped_labels_and_negatives():
    rows = colorado.parse_board_rows(JBC_TEXT, "TABLE 1")
    assert rows["ASU"][0] == 21_009_471  # the row before the marker is ignored
    assert rows["CMU"][0] == 40_143_534  # label wrapped onto two lines
    assert rows["CSU"][0] == 202_360_491 and rows["CU"][0] == 275_755_786
    assert rows["CMC"][0] == 10_831_151 and "CSM" not in rows
    assert colorado.pick(rows["CCCS"], -1) == 189_865_735 - 110_122_127
    assert colorado.pick(rows["ATC"], 1) == 19_642_162


def test_fiscal_year_cpi_needs_a_full_july_june_year():
    lines = [f"CUURS48BSA0\t2024\tM{m:02d}\t{100 + m}\t" for m in (7, 9, 11)]
    lines += [f"CUURS48BSA0\t2025\tM{m:02d}\t{110 + m}\t" for m in (1, 3, 5, 7)]
    lines += ["CUURS48BSA0\t2024\tM13\t999\t", "CUUROTHER\t2024\tM07\t1\t"]
    cpi = colorado.fiscal_year_cpi(lines)
    assert cpi == {"FY 2024-25": round((107 + 109 + 111 + 111 + 113 + 115) / 6, 3)}


def test_per_fte_handles_missing():
    assert colorado.per_fte(1_000_000, 250) == 4000
    assert colorado.per_fte(None, 250) is None and colorado.per_fte(5, 0) is None


BUILT = Path("dashboard/data/colorado.json")


@pytest.mark.skipif(not BUILT.exists(), reason="dashboard data not built")
def test_built_panel_matches_published_totals():
    data = json.loads(BUILT.read_text())
    fy = data["meta"]["fundingYears"]
    boards = {b["id"]: b for b in data["boards"]}
    total = lambda y: sum(b["funding"][fy.index(y)] for b in data["boards"])  # noqa: E731
    # JBC table totals (rounded to the dollar in the source tables).
    assert total("FY 2019-20") == 850_323_630
    assert total("FY 2020-21") == 850_323_630 - 493_187_703
    assert abs(total("FY 2025-26") - 1_298_029_725) <= 2
    assert sum(b["crf"] for b in data["boards"]) == 450_000_000
    state = sum(boards[b]["funding"][fy.index("FY 2024-25")] for b in colorado.STATE_BOARDS)
    assert state == 1_215_487_423
    # CDHE Public Summary for resident FTE, within rounding.
    years = data["meta"]["fteYears"]
    resident = [sum(i["resident"][k] or 0 for i in data["institutions"]) for k in range(len(years))]
    assert abs(resident[years.index("FY 2024-25")] - 148_445) <= 5
    assert abs(resident[years.index("FY 2010-11")] - 166_355) <= 5
    assert data["meta"]["deflator"]["FY 2025-26"] == 1.0
