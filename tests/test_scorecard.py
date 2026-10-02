"""Offline tests for the College Scorecard merge."""

import pandas as pd

from src.ingest import scorecard


def _raw(rows):
    cols = ["UNITID", "OPEID6", "MAIN", "MD_EARN_WNE_4YR", "MD_EARN_WNE_P10", "GRAD_DEBT_MDN"]
    return pd.DataFrame(rows, columns=cols, dtype=str)


def test_tidy_treats_suppressed_and_null_as_missing():
    sc = scorecard.tidy(
        _raw(
            [
                ("1", "1234", "1", "50000", "PrivacySuppressed", "NULL"),
                ("2", None, "1", "0", "40000", "12000"),
            ]
        )
    )
    assert sc.loc[1, "opeid6"] == "001234"  # zero-padded to 6 digits
    assert sc.loc[1, "earnings4yr"] == 50000
    assert pd.isna(sc.loc[1, "earnings10yr"]) and pd.isna(sc.loc[1, "gradDebt"])
    assert pd.isna(sc.loc[2, "earnings4yr"])  # 0 is not a real median
    recs = [{"id": 2, "fte": 10}]
    scorecard.attach(recs, sc)
    assert recs[0]["opeid6"] is None  # no NaN leaks into the JSON
    assert recs[0]["scShared"] is None and recs[0]["earnings10yr"] == 40000


def test_attach_anchors_each_family_on_its_main_campus():
    # Scorecard repeats family-level values on every campus in the family.
    sc = scorecard.tidy(
        _raw(
            [
                ("10", "000777", "1", "60000", "55000", "20000"),  # main, smaller
                ("11", "000777", "0", "60000", "55000", "20000"),  # branch, larger
                ("12", "000888", "1", "40000", "35000", "9000"),  # single campus
            ]
        )
    )
    recs = [{"id": 10, "fte": 500}, {"id": 11, "fte": 9000}, {"id": 12, "fte": 100}, {"id": 13}]
    meta = scorecard.attach(recs, sc)
    by = {r["id"]: r for r in recs}
    assert by[10]["scAnchor"] and not by[11]["scAnchor"]
    assert by[10]["scShared"] == by[11]["scShared"] == 2
    assert by[12]["scShared"] == 1 and by[12]["scAnchor"]
    assert by[13]["earnings4yr"] is None and by[13]["opeid6"] is None  # unmatched
    assert meta["matched"] == 3 and meta["families"] == 1


def test_attach_falls_back_to_largest_campus_without_main_flag():
    sc = scorecard.tidy(
        _raw(
            [
                ("20", "000999", "0", "50000", "45000", "15000"),
                ("21", "000999", "0", "50000", "45000", "15000"),
            ]
        )
    )
    recs = [{"id": 20, "fte": 300}, {"id": 21, "fte": 3000}]
    scorecard.attach(recs, sc)
    assert [r["scAnchor"] for r in recs] == [False, True]
