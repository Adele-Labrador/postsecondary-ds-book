"""Tests for ipeds_utils.

The offline tests cover the logic that is easy to get wrong and expensive to debug
later: reserved-code masking, suppression, pseudonymisation, and validation semantics.
The network tests are marked so the suite stays usable without internet.

    pytest tests/ -v            # everything
    pytest tests/ -v -m "not network"
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ipeds_utils as iu  # noqa: E402

# --- Validation semantics -------------------------------------------------------


def test_unique_key_flags_duplicates():
    frame = pd.DataFrame({"UNITID": [1, 1, 2]})
    report = iu.validate(frame, [iu.unique_key("UNITID")], "t")
    assert report.results[0]["n_offending"] == 2
    assert not report.ok


def test_passing_rule_reports_zero():
    frame = pd.DataFrame({"UNITID": [1, 2, 3]})
    assert iu.validate(frame, [iu.unique_key("UNITID")], "t").ok


def test_warn_severity_does_not_fail_the_run():
    frame = pd.DataFrame({"UNITID": [1], "X": [-5]})
    report = iu.validate(frame, [iu.in_range("X", 0, None, severity="warn")], "t")
    assert report.results[0]["n_offending"] == 1
    assert report.ok, "warn-level findings must not fail the report"


def test_broken_rule_is_recorded_not_raised():
    frame = pd.DataFrame({"UNITID": [1]})
    bad = iu.Rule("explodes", lambda d: d["NOPE"] > 0)
    report = iu.validate(frame, [bad], "t")
    assert report.results[0]["status"] == "error"
    assert not report.ok


def test_sums_to_respects_tolerance():
    frame = pd.DataFrame({"T": [100.0], "A": [60.0], "B": [39.0]})
    assert iu.validate(frame, [iu.sums_to("T", ["A", "B"])], "t").results[0]["n_offending"] == 1
    assert iu.validate(frame, [iu.sums_to("T", ["A", "B"], tolerance=1)], "t").ok


def test_sums_to_ignores_rows_with_missing_total():
    frame = pd.DataFrame({"T": [np.nan], "A": [1.0], "B": [2.0]})
    assert iu.validate(frame, [iu.sums_to("T", ["A", "B"])], "t").ok


def test_subset_of_catches_unknown_codes():
    frame = pd.DataFrame({"UNITID": [1, 2], "CONTROL": [1, 9]})
    report = iu.validate(frame, [iu.subset_of("CONTROL", {1, 2, 3})], "t")
    assert report.results[0]["n_offending"] == 1


def test_report_raise_if_failed():
    frame = pd.DataFrame({"UNITID": [1, 1]})
    with pytest.raises(AssertionError):
        iu.validate(frame, [iu.unique_key("UNITID")], "t").raise_if_failed()


# --- De-identification ----------------------------------------------------------


def test_suppress_blanks_small_cells_but_not_zero():
    frame = pd.DataFrame({"UNITID": [1, 2, 3], "N": [4, 25, 0]})
    out, audit = iu.suppress(frame, ["N"], threshold=10, complementary=False)
    assert pd.isna(out.loc[0, "N"]), "4 is below threshold and must be suppressed"
    assert out.loc[1, "N"] == 25
    assert out.loc[2, "N"] == 0, "a true zero is not a small cell"
    assert audit.loc[0, "n_suppressed"] == 1


def test_complementary_suppression_blanks_a_second_cell():
    frame = pd.DataFrame({"UNITID": [1, 2, 3], "G": ["a", "a", "a"], "N": [3, 40, 55]})
    out, _ = iu.suppress(frame, ["N"], threshold=10, complementary=True, group_cols=["G"])
    assert out["N"].isna().sum() == 2, "a lone suppression is recoverable by subtraction"


def test_synthetic_id_is_deterministic_and_salt_dependent():
    ids = pd.Series([100654, 100663])
    a = iu.synthetic_id(ids, salt="s1")
    b = iu.synthetic_id(ids, salt="s1")
    c = iu.synthetic_id(ids, salt="s2")
    assert list(a) == list(b), "same salt must give stable pseudonyms across runs"
    assert list(a) != list(c), "different salts must give different pseudonyms"


def test_synthetic_id_rejects_placeholder_salt():
    with pytest.raises(ValueError):
        iu.synthetic_id(pd.Series([1]), salt="changeme")


def test_k_anonymity_identifies_singletons():
    frame = pd.DataFrame({"BAND": ["S", "S", "L"]})
    result = iu.k_anonymity(frame, ["BAND"])
    assert result["at_risk"].sum() == 1


# --- Dictionary helpers ---------------------------------------------------------


def test_imputation_partner_naming():
    assert iu.imputation_partner("ret_pcf") == "XRET_PCF"


# --- Network-dependent behaviour ------------------------------------------------


@pytest.mark.network
def test_fetch_and_read_directory():
    record = iu.fetch("HD2023", raw_dir="data/raw")
    assert record["data_bytes"] > 0
    assert len(record["data_sha256"]) == 64

    frame = iu.read_csv(record["data_path"], usecols=["UNITID", "INSTNM", "CONTROL"])
    assert len(frame) > 5_000
    assert frame["UNITID"].is_unique
    assert str(frame["UNITID"].dtype) == "Int64"


@pytest.mark.network
def test_read_csv_is_case_insensitive_on_usecols():
    record = iu.fetch("HD2023", raw_dir="data/raw")
    upper = iu.read_csv(record["data_path"], usecols=["UNITID", "INSTNM"])
    lower = iu.read_csv(record["data_path"], usecols=["unitid", "instnm"])
    assert list(upper.columns) == list(lower.columns) == ["UNITID", "INSTNM"]


@pytest.mark.network
def test_read_csv_raises_a_useful_error_for_absent_columns():
    record = iu.fetch("HD2023", raw_dir="data/raw")
    with pytest.raises(KeyError, match="NOTACOLUMN"):
        iu.read_csv(record["data_path"], usecols=["UNITID", "NOTACOLUMN"])


@pytest.mark.network
def test_reference_period_assertion_rejects_the_wrong_period():
    record = iu.fetch("HD2023", raw_dir="data/raw")
    iu.assert_reference_period(record["dict_path"], expect=r"2023-24", table="HD2023")
    with pytest.raises(AssertionError):
        iu.assert_reference_period(record["dict_path"], expect=r"1998-99", table="HD2023")


@pytest.mark.network
def test_dictionary_parses_despite_casing_variation():
    # EF2023C uses "Varlist" rather than "varlist"; C2023_A uses "varName".
    for table in ("EF2023C", "C2023_A"):
        record = iu.fetch(table, raw_dir="data/raw")
        variables = iu.read_dict(record["dict_path"])
        assert "varname" in variables.columns
        assert "UNITID" in set(variables["varname"].str.upper())


@pytest.mark.network
def test_library_expenditures_reconcile_exactly():
    """LEXPTOT decomposes into salaries, benefits, materials, and operations."""
    record = iu.fetch("AL2023", raw_dir="data/raw")
    frame = iu.read_csv(record["data_path"])
    parts = ["LSALWAG", "LFRNGBN", "LEXMSTL", "LEXOMTL"]
    for col in parts + ["LEXPTOT"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").mask(lambda s: s < 0)
    complete = frame[frame[parts + ["LEXPTOT"]].notna().all(axis=1)]
    gap = (complete[parts].sum(axis=1) - complete["LEXPTOT"]).abs()
    assert len(complete) > 2_000
    assert (gap > 1).sum() == 0, "fringe benefits are part of the total"


@pytest.mark.network
def test_graduation_rate_grain_is_unitid_by_grtype():
    record = iu.fetch("GR2023", raw_dir="data/raw")
    frame = iu.read_csv(record["data_path"], usecols=["UNITID", "GRTYPE", "GRTOTLT"])
    assert not frame.duplicated(["UNITID", "GRTYPE"]).any()


# --- Rules fail loudly on missing columns (v1.1) --------------------------------


@pytest.mark.parametrize(
    "rule",
    [
        iu.in_range("GONE", 0, 1),
        iu.sums_to("GONE", ["A"]),
        iu.sums_to("T", ["A", "GONE"]),
        iu.subset_of("GONE", {1}),
        iu.referential("GONE", {1}),
    ],
    ids=["in_range", "sums_to_total", "sums_to_part", "subset_of", "referential"],
)
def test_rule_on_missing_column_fails_rather_than_passes(rule):
    frame = pd.DataFrame({"UNITID": [1], "T": [1], "A": [1]})
    report = iu.validate(frame, [rule], "t")
    assert report.results[0]["status"] == "error"
    assert not report.ok, "a renamed column must not look like clean data"


def test_rolls_up_accepts_consistent_totals_and_flags_broken_ones():
    frame = pd.DataFrame(
        {
            "UNITID": [1, 1, 1, 2, 2, 2],
            "AWLEVEL": [5] * 6,
            "CIPCODE": ["99", "01.0000", "13.0100"] * 2,
            "CTOTALT": [10, 4, 6, 10, 4, 5],  # institution 2 does not reconcile
        }
    )
    rule = iu.rolls_up("CTOTALT", level="CIPCODE", total_code="99", keys=["UNITID", "AWLEVEL"])
    report = iu.validate(frame, [rule], "t")
    assert report.results[0]["n_offending"] == 1
    assert report.results[0]["sample_unitids"] == ["2"]


# --- Statistics helpers ---------------------------------------------------------


def test_robust_z_ignores_a_single_extreme_value():
    values = pd.Series([10, 11, 12, 13, 14, 10_000])
    z = iu.robust_z(values)
    assert abs(z.iloc[2]) < 1, "the bulk of the data must stay near zero"
    assert z.iloc[-1] > 100


def test_robust_z_returns_nan_when_mad_is_zero():
    assert iu.robust_z([5, 5, 5, 9]).isna().all()


def test_cliffs_delta_matches_pairwise_definition():
    x, y = [1, 2, 3, 4], [2, 3]
    pairwise = np.mean([np.sign(a - b) for a in x for b in y])
    assert iu.cliffs_delta(x, y) == pytest.approx(pairwise)


def test_beta_binomial_recovers_known_prior():
    rng = np.random.default_rng(7)
    n = rng.integers(20, 400, size=3000)
    p = rng.beta(12, 8, size=3000)
    k = rng.binomial(n, p)
    a, b = iu.fit_beta_binomial(k, n)
    assert a / (a + b) == pytest.approx(0.6, abs=0.01)
    assert a + b == pytest.approx(20, rel=0.15)


def test_shrinkage_weight_grows_with_cohort_size():
    post = iu.shrink(pd.Series([1, 100]), pd.Series([2, 200]), a=12, b=8)
    assert post["weight"].iloc[0] < 0.1 < 0.9 < post["weight"].iloc[1]
    assert post["post_mean"].iloc[0] == pytest.approx(13 / 22)


def test_within_transform_removes_entity_means():
    frame = pd.DataFrame({"UNITID": [1, 1, 2, 2], "Y": [10.0, 12.0, 50.0, 54.0]})
    out = iu.within_transform(frame, "UNITID", ["Y"])
    assert out.groupby("UNITID")["Y"].mean().abs().max() < 1e-12
    assert out["Y"].tolist() == [-1.0, 1.0, -2.0, 2.0]


def test_tenure_density_is_nan_not_zero_without_staff():
    sis = pd.DataFrame(
        {"UNITID": [1, 1, 1, 2], "FACSTAT": [0, 20, 30, 0], "SISTOTL": [100, 30, 10, 0]}
    )
    out = iu.tenure_density(sis).set_index("UNITID")
    assert out.loc[1, "TENURE_DENSITY"] == pytest.approx(0.4)
    assert np.isnan(out.loc[2, "TENURE_DENSITY"])


def test_balanced_panel_drops_entities_with_gaps():
    panel = pd.DataFrame(
        {"UNITID": [1, 1, 2, 2], "YEAR": [2022, 2023] * 2, "V": [1.0, 2.0, 3.0, np.nan]}
    )
    assert iu.balanced(panel, "V")["UNITID"].unique().tolist() == [1]


# --- Code columns stay text (v1.1) ------------------------------------------------


@pytest.mark.network
def test_cipcode_and_opeid_keep_their_text_form():
    comp = iu.read_csv(
        iu.fetch("C2023_A", raw_dir="data/raw")["data_path"], usecols=["UNITID", "CIPCODE"]
    )
    assert "01.0000" in set(comp["CIPCODE"]), "CIP codes must not be parsed as floats"
    hd = iu.read_csv(
        iu.fetch("HD2023", raw_dir="data/raw")["data_path"], usecols=["UNITID", "OPEID"]
    )
    assert hd["OPEID"].str.len().eq(8).mean() > 0.99
    assert hd["OPEID"].str.startswith("0").any(), "leading zeros must survive"


@pytest.mark.network
def test_cip99_rows_equal_the_sum_of_programme_rows():
    comp = iu.read_csv(
        iu.fetch("C2023_A", raw_dir="data/raw")["data_path"],
        usecols=["UNITID", "CIPCODE", "AWLEVEL", "MAJORNUM", "CTOTALT"],
    )
    rule = iu.rolls_up(
        "CTOTALT", level="CIPCODE", total_code="99", keys=["UNITID", "AWLEVEL", "MAJORNUM"]
    )
    assert iu.validate(comp, [rule], "C2023_A").ok


@pytest.mark.network
def test_dot_missing_marker_is_read_as_missing_not_text():
    frame = iu.read_csv(
        iu.fetch("DRVC2023", raw_dir="data/raw")["data_path"], usecols=["UNITID", "BASDEG"]
    )
    assert pd.api.types.is_numeric_dtype(frame["BASDEG"]), "'.' must not make the column text"
    assert frame["BASDEG"].isna().sum() > 1000


def test_decode_survives_float_conversion_from_masking():
    valuesets = pd.DataFrame(
        {
            "varname": ["SECTOR"] * 2,
            "codevalue": ["1", "2"],
            "valuelabel": ["Public, 4-year or above", "Private not-for-profit, 4-year or above"],
        }
    )
    frame = pd.DataFrame({"SECTOR": [1.0, 2.0, np.nan]})  # as left by reserved-code masking
    out = iu.decode(frame, valuesets, "SECTOR")
    assert out["SECTOR_LABEL"].tolist()[:2] == [
        "Public, 4-year or above",
        "Private not-for-profit, 4-year or above",
    ]


def test_code_key_keeps_significant_zeros():
    got = iu.code_key(pd.Series(["01.0000", "10.0000", "13.0100", "3.0", "99", "-2.0", "0.0"]))
    assert got.tolist() == ["01.0000", "10.0000", "13.0100", "3", "99", "-2", "0"]


def test_k_anonymity_refuses_absent_quasi_identifiers():
    with pytest.raises(KeyError):
        iu.k_anonymity(pd.DataFrame({"A": [1, 2]}), ["A", "B"])


def test_peer_feature_matrix_transforms_and_drops_incomplete_rows():
    inst = pd.DataFrame(
        {"UNITID": [1, 2, 3], "ENROLL_FALL": [100, 1000, np.nan], "TUITION_SHARE": [1.4, 0.5, 0.2]}
    )
    spec = {"log_enroll": ("ENROLL_FALL", "log10"), "tuition": ("TUITION_SHARE", "clip01")}
    X, coverage = iu.peer_feature_matrix(inst, features=spec)
    assert X.index.tolist() == [1, 2]
    assert X["log_enroll"].tolist() == [2.0, 3.0]
    assert X.loc[1, "tuition"] == 1.0
    assert coverage.loc["log_enroll", "missing"] == 1


def test_suppress_refuses_absent_columns():
    with pytest.raises(KeyError):
        iu.suppress(pd.DataFrame({"N": [1]}), ["N", "MISSING"])


def test_suppress_counts_single_cell_groups_it_cannot_protect():
    frame = pd.DataFrame({"G": [1, 2, 2], "N": [3, 3, 40]})
    out, audit = iu.suppress(frame, ["N"], threshold=5, group_cols=["G"])
    assert out["N"].isna().tolist() == [True, True, True]
    assert audit.loc[0, "groups_needing_total_suppressed"] == 1
