"""Assemble the institution-level analytic table used by the ten analysis notebooks.

The twelve component notebooks each curate one survey at its native grain. Analysis
needs one row per institution with columns from many surveys, most of which already
exist, pre-aggregated, in the NCES derived (``DRV*``) files. This module is the single
place where those pieces are joined, so the joins, the reference-period checks, and
the engineered ratios are defined once and tested once.

Nothing here reads a column without checking its reference period against the file's
Introduction sheet. The one exception, ``DRVEF122023``, is recorded with its reason.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .dictionary import assert_reference_period
from .fetch import fetch
from .io import read_curated
from .schema import read_csv

# ---------------------------------------------------------------------------------
# Companion tables: one row per UNITID, taken directly from the Data Center.
# ``period`` is a regex that must appear in the Introduction sheet; ``None`` requires
# a ``why`` explaining where the period comes from instead.
# ---------------------------------------------------------------------------------
COMPANIONS: dict[str, dict] = {
    "EF2023D": {
        "cols": ["RET_PCF", "RET_PCP", "STUFACR", "RRFTCTA", "GRCOHRT"],
        "period": r"Fall 2023",
    },
    "DRVEF2023": {
        "cols": ["ENRTOT", "EFUG", "FTE", "PCTENRW"],
        "period": r"Fall 2023",
    },
    "DRVEF122023": {
        "cols": ["UNDUP", "UNDUPUG", "FTE12MN", "PCTE12DEEXC", "E12UG1ST"],
        "period": None,
        "why": (
            "The Introduction sheet is empty in this release. The 12-month reporting "
            "period, July 1, 2022 to June 30, 2023, is asserted on EFFY2023 in c03_e12."
        ),
    },
    "DRVGR2023": {"cols": ["GRRTTOT", "GBA6RTT"], "period": r"cohort year 2017"},
    "GR200_23": {
        "cols": ["BAAC150", "BANC150", "BAGR150", "L4AC150", "L4NC150"],
        "period": r"cohort year 2015",
    },
    "DRVADM2023": {"cols": ["DVADM01", "DVADM04"], "period": r"Fall 2023"},
    "SFA2223": {"cols": ["UAGRNTP", "UPGRNTP", "AGRNT_A"], "period": r"2022-23"},
    "DRVHR2023": {
        "cols": ["SFTEINST", "SFTERSRC", "SFTEPBSV", "SFTEMNGM", "SFTEOFAS", "SFTETOTL", "SALTOTL"],
        "period": r"Fall 2023",
    },
    "DRVAL2023": {
        "cols": ["LEXPTOTF", "LTOTLFTE", "LEBOOKSP", "LEXMSCSP"],
        "period": r"Fiscal year 2023",
    },
    "DRVIC2023": {
        "cols": ["TUFEYR0", "TUFEYR1", "TUFEYR2", "TUFEYR3", "CINSON", "COTSON"],
        "period": r"2023-24",
    },
    "IC2023_AY": {"cols": ["CHG2AY3", "CHG3AY3"], "period": r"2023-24"},
    "DRVOM2023": {
        "cols": ["OM1TOTLAWDP8", "OM1PELLAWDP8", "OM1NPELAWDP8"],
        "period": r"2015-16 cohort",
    },
    "DRVC2023": {
        "cols": ["ASCDEG", "BASDEG", "MASDEG", "DOCDEGRS"],
        "period": r"July 1, 2022",
    },
}

# HD categorical fields use negative reserved codes (-1 not reported, -2 not
# applicable, -3 not available). They are valid labels for decoding but must never
# enter arithmetic or be treated as ordered values.
HD_RESERVED_CODES = (-1, -2, -3)

TENURE_CODES = {"all": 0, "tenured": 20, "on_track": 30}  # S2023_SIS FACSTAT
ALL_RANKS = 7  # SAL2023_IS ARANK "All instructional staff total"


def load_companion(table: str, raw_dir="data/raw", *, cols=None) -> tuple[pd.DataFrame, dict]:
    """Fetch one companion table, assert its period, and return UNITID-keyed columns."""
    spec = COMPANIONS[table]
    cols = cols or spec["cols"]
    record = fetch(table, raw_dir=raw_dir)
    if spec["period"] is not None:
        assert_reference_period(record["dict_path"], expect=spec["period"], table=table)
        record["period_check"] = spec["period"]
    else:
        record["period_check"] = f"not assertable: {spec['why']}"
    frame = read_csv(record["data_path"], usecols=["UNITID", *cols])
    if frame["UNITID"].duplicated().any():
        raise ValueError(f"{table} is not one row per UNITID; it needs a reshape, not a join")
    return frame, record


def tenure_density(sis: pd.DataFrame) -> pd.DataFrame:
    """Tenured plus tenure-track share of full-time instructional staff (``S2023_SIS``).

    ``S2023_SIS`` is long on ``FACSTAT``. Code 0 is the all-staff total, 20 tenured,
    30 on tenure track. Institutions with no full-time instructional staff get NaN,
    not 0: a share of nothing is undefined, and a zero would read as "no tenure".
    """
    wide = sis.pivot_table(index="UNITID", columns="FACSTAT", values="SISTOTL", aggfunc="sum")
    total = wide.get(TENURE_CODES["all"])
    tenure = wide.get(TENURE_CODES["tenured"], 0).fillna(0) + wide.get(
        TENURE_CODES["on_track"], 0
    ).fillna(0)
    out = pd.DataFrame(
        {
            "FT_INSTR_STAFF": total,
            "TENURE_DENSITY": (tenure / total).where(total > 0),
        }
    )
    return out.reset_index()


def salary_equity(sal: pd.DataFrame) -> pd.DataFrame:
    """Women's average 9-month-equated salary as a share of men's, all ranks.

    Computed on the ``ARANK == 7`` total row of ``SAL2023_IS``. This is an unadjusted
    ratio: it mixes rank composition with within-rank pay differences, and is
    presented in the scorecard as a prompt for investigation, not as a finding of
    pay discrimination.
    """
    total = sal.loc[sal["ARANK"] == ALL_RANKS, ["UNITID", "SAEQ9AM", "SAEQ9AW"]]
    total = total.rename(columns={"SAEQ9AM": "SAL_MEN", "SAEQ9AW": "SAL_WOMEN"})
    ratio = total["SAL_WOMEN"] / total["SAL_MEN"]
    total["SAL_W_TO_M"] = ratio.where(total["SAL_MEN"] > 0)
    return total


def _mask_reserved(frame: pd.DataFrame, cols) -> pd.DataFrame:
    for col in cols:
        if col in frame.columns:
            frame[col] = frame[col].mask(frame[col].isin(HD_RESERVED_CODES))
    return frame


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    return (num / den).where(den > 0)


# Where each analytic column comes from, for the data dictionary written by notebook 01.
COLUMN_SOURCES: dict[str, str] = {
    "ENROLL_FALL": "c04_ef EFTOTLT at EFALEVEL 1 (all students total)",
    "AWARDS_TOTAL": "c05_c CTOTALT, CIPCODE '99' first-major rows summed over AWLEVEL",
    "TUITION_SHARE": "c10_f TUITION_REVENUE / TOTAL_REVENUES",
    "INSTR_EXP_SHARE": "c10_f INSTRUCTION_EXPENSE / TOTAL_EXPENSES",
    "EXP_PER_FTE": "c10_f TOTAL_EXPENSES / DRVEF2023 FTE",
    "INSTR_FTE_SHARE": "DRVHR2023 SFTEINST / SFTETOTL",
    "MGMT_FTE_SHARE": "DRVHR2023 SFTEMNGM / SFTETOTL",
    "TENURE_DENSITY": "S2023_SIS (FACSTAT 20 + 30) / FACSTAT 0",
    "SAL_W_TO_M": "SAL2023_IS SAEQ9AW / SAEQ9AM at ARANK 7",
    "PELL_GAP": "DRVOM2023 OM1PELLAWDP8 - OM1NPELAWDP8 (percentage points)",
    "TWELVE_TO_FALL": "DRVEF122023 UNDUP / DRVEF2023 ENRTOT",
    "BA_RATE_150": "GR200_23 BANC150 / BAAC150",
    "L4_RATE_150": "GR200_23 L4NC150 / L4AC150",
    "ADMIT_RATE": "DRVADM2023 DVADM01 (percent)",
    "YIELD": "DRVADM2023 DVADM04 (percent)",
    "LIB_FROM_PARENT": "DRVAL2023 row with no AL2023 report; library columns blanked",
}


def institution_table(
    curated_root="data/curated", raw_dir="data/raw"
) -> tuple[pd.DataFrame, list[dict]]:
    """Build the one-row-per-institution analytic table and its provenance.

    Returns
    -------
    (frame, provenance)
        ``frame`` is keyed on ``UNITID``. ``provenance`` lists every companion file
        read, with digests and the period check that was applied.
    """
    hd, _ = read_curated("c01_ic", root=curated_root)
    base = hd[
        [
            "UNITID",
            "INSTNM",
            "STABBR",
            "OBEREG",
            "SECTOR",
            "CONTROL",
            "ICLEVEL",
            "HLOFFER",
            "C21BASIC",
            "LOCALE",
            "HBCU",
            "TRIBAL",
            "CYACTIVE",
            "SECTOR_LABEL",
            "CONTROL_LABEL",
            "ICLEVEL_LABEL",
            "C21BASIC_LABEL",
        ]
    ].copy()
    base = _mask_reserved(base, ["SECTOR", "CONTROL", "ICLEVEL", "HLOFFER", "C21BASIC", "LOCALE"])

    ef, _ = read_curated("c04_ef", root=curated_root)
    enroll = ef.loc[ef["EFALEVEL"] == 1, ["UNITID", "EFTOTLT"]].rename(
        columns={"EFTOTLT": "ENROLL_FALL"}
    )

    comp, _ = read_curated("c05_c", root=curated_root)
    total_rows = comp[(comp["CIPCODE"].astype(str) == "99") & (comp["MAJORNUM"] == 1)]
    awards = (
        total_rows.groupby("UNITID", as_index=False)["CTOTALT"]
        .sum()
        .rename(columns={"CTOTALT": "AWARDS_TOTAL"})
    )

    fin, _ = read_curated("c10_f", root=curated_root)
    adm, _ = read_curated("c02_adm", root=curated_root)
    adm = adm[
        [
            "UNITID",
            "APPLCN",
            "ADMSSN",
            "ENRLT",
            "SATVR25",
            "SATVR75",
            "SATMT25",
            "SATMT75",
            "ACTCM25",
            "ACTCM75",
        ]
    ]
    sfa, _ = read_curated("c09_sfa", root=curated_root)
    sfa = sfa[["UNITID", "PGRNT_P", "FGRNT_A", "NPIST2"]]
    al, _ = read_curated("c12_al", root=curated_root)
    al = al[["UNITID", "LEXP100K"]]

    frame = base
    for part in (enroll, awards, fin, adm, sfa, al):
        frame = frame.merge(part, on="UNITID", how="left", validate="one_to_one")

    provenance: list[dict] = []
    for table in COMPANIONS:
        part, record = load_companion(table, raw_dir=raw_dir)
        provenance.append(record)
        frame = frame.merge(part, on="UNITID", how="left", validate="one_to_one")

    long_tables = (
        ("S2023_SIS", tenure_density, r"Fall 2023"),
        ("SAL2023_IS", salary_equity, r"2023-24"),
    )
    for table, builder, expect in long_tables:
        record = fetch(table, raw_dir=raw_dir)
        assert_reference_period(record["dict_path"], expect=expect, table=table)
        record["period_check"] = expect
        provenance.append(record)
        cols = (
            ["UNITID", "FACSTAT", "SISTOTL"]
            if table == "S2023_SIS"
            else ["UNITID", "ARANK", "SAEQ9AM", "SAEQ9AW"]
        )
        frame = frame.merge(
            builder(read_csv(record["data_path"], usecols=cols)),
            on="UNITID",
            how="left",
            validate="one_to_one",
        )

    # Engineered features. Every ratio is NaN, never inf, when its denominator is 0.
    frame["LOG_ENROLL"] = np.log10(frame["ENROLL_FALL"].where(frame["ENROLL_FALL"] > 0))
    frame["TUITION_SHARE"] = _safe_ratio(frame["TUITION_REVENUE"], frame["TOTAL_REVENUES"])
    frame["INSTR_EXP_SHARE"] = _safe_ratio(frame["INSTRUCTION_EXPENSE"], frame["TOTAL_EXPENSES"])
    frame["EXP_PER_FTE"] = _safe_ratio(frame["TOTAL_EXPENSES"], frame["FTE"])
    frame["INSTR_FTE_SHARE"] = _safe_ratio(frame["SFTEINST"], frame["SFTETOTL"])
    frame["MGMT_FTE_SHARE"] = _safe_ratio(frame["SFTEMNGM"], frame["SFTETOTL"])
    frame["PELL_GAP"] = frame["OM1PELLAWDP8"] - frame["OM1NPELAWDP8"]
    frame["TWELVE_TO_FALL"] = _safe_ratio(frame["UNDUP"], frame["ENRTOT"])
    frame["BA_RATE_150"] = _safe_ratio(frame["BANC150"], frame["BAAC150"])
    frame["L4_RATE_150"] = _safe_ratio(frame["L4NC150"], frame["L4AC150"])
    frame["ADMIT_RATE"] = frame["DVADM01"]
    frame["YIELD"] = frame["DVADM04"]

    # DRVAL2023 carries rows for campuses that filed no Academic Libraries report of
    # their own. In FY2023 all 273 such rows repeat, exactly, the expenditure-share
    # profile of a campus that did report: the derived file attributes a parent's
    # library to its children while LEXPTOTF still divides by the child's own FTE.
    # Those values are not the campus's data, so they are flagged and blanked.
    lib_cols = ["LEXPTOTF", "LTOTLFTE", "LEBOOKSP", "LEXMSCSP"]
    frame["LIB_FROM_PARENT"] = frame["LEXP100K"].isna() & frame[lib_cols].notna().any(axis=1)
    frame.loc[frame["LIB_FROM_PARENT"], lib_cols] = np.nan
    return frame, provenance


def stack_vintages(
    template: str,
    years,
    cols: list[str],
    *,
    raw_dir="data/raw",
    period_template: str = r"Fall {year}",
) -> tuple[pd.DataFrame, list[dict]]:
    """Stack several annual releases of one table into a long ``UNITID`` x ``YEAR`` panel.

    Each vintage is checked against its own Introduction sheet, so a file that is
    mislabelled, or a period that shifts between releases, fails here rather than
    surfacing as a trend break. Revised (``_rv``) releases are preferred by ``fetch``.

    ``template`` and ``period_template`` take a ``{year}`` placeholder, e.g.
    ``stack_vintages("EF{year}D", range(2018, 2024), ["RET_PCF"])``.
    """
    frames, provenance = [], []
    for year in years:
        table = template.format(year=year)
        record = fetch(table, raw_dir=raw_dir)
        expect = period_template.format(year=year)
        assert_reference_period(record["dict_path"], expect=expect, table=table)
        record["period_check"] = expect
        part = read_csv(record["data_path"], usecols=["UNITID", *cols])
        part.insert(1, "YEAR", int(year))
        frames.append(part)
        provenance.append(record)
    panel = pd.concat(frames, ignore_index=True)
    if panel.duplicated(["UNITID", "YEAR"]).any():
        raise ValueError(f"{template} vintages are not one row per UNITID and year")
    return panel, provenance


def balanced(panel: pd.DataFrame, value: str, *, entity="UNITID", time="YEAR") -> pd.DataFrame:
    """Restrict a long panel to entities observed with non-missing ``value`` every period.

    Unbalanced panels confound composition with change: if closing institutions had
    lower retention, the sector mean rises as they drop out even when no surviving
    institution improved. Compare both versions before interpreting a trend.
    """
    observed = panel.dropna(subset=[value])
    n_periods = observed[time].nunique()
    counts = observed.groupby(entity)[time].nunique()
    keep = counts.index[counts == n_periods]
    return observed[observed[entity].isin(keep)].copy()


# ---------------------------------------------------------------------------------
# Peer-group feature matrix, shared by clustering (05), PCA (06), and benchmarking (10)
# ---------------------------------------------------------------------------------

# name -> (source column, transform). Logs are base 10 so coefficients read as orders
# of magnitude. Shares are clipped to [0, 1]: a tuition share above 1 is real (other
# revenue was negative) but would dominate a distance metric.
PEER_FEATURES: dict[str, tuple[str, str]] = {
    "log_enroll": ("ENROLL_FALL", "log10"),
    "stu_fac_ratio": ("STUFACR", "none"),
    "tuition_share": ("TUITION_SHARE", "clip01"),
    "instr_exp_share": ("INSTR_EXP_SHARE", "clip01"),
    "log_exp_per_fte": ("EXP_PER_FTE", "log10"),
    "instr_fte_share": ("INSTR_FTE_SHARE", "clip01"),
    "tenure_density": ("TENURE_DENSITY", "clip01"),
    "log_avg_salary": ("SALTOTL", "log10"),
    "pct_online": ("PCTE12DEEXC", "none"),
    "pct_pell": ("UPGRNTP", "none"),
}


def peer_feature_matrix(inst: pd.DataFrame, *, features=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Transformed peer features, one row per UNITID, and a coverage report.

    Rows with any missing feature are dropped rather than imputed. For clustering this
    is the conservative choice: an imputed median places an institution at the centre
    of the feature space, which is exactly where cluster boundaries are least stable.
    The coverage report says how many institutions each feature removes.
    """
    features = features or PEER_FEATURES
    out = pd.DataFrame(index=inst["UNITID"].values)
    for name, (col, how) in features.items():
        x = pd.to_numeric(inst[col], errors="coerce").to_numpy(dtype=float)
        if how == "log10":
            x = np.where(x > 0, np.log10(np.where(x > 0, x, 1.0)), np.nan)
        elif how == "clip01":
            x = np.clip(x, 0, 1)
        out[name] = x
    out.index.name = "UNITID"
    coverage = pd.DataFrame(
        {
            "source": [c for c, _ in features.values()],
            "missing": out.isna().sum().values,
            "share_missing": out.isna().mean().round(3).values,
        },
        index=list(features),
    )
    return out.dropna(), coverage
