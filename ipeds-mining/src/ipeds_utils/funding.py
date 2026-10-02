"""Colorado HB 20-1366 Step 2 performance-funding mechanics.

Implements the allocation arithmetic documented in CDHE's *Colorado Performance
Funding Overview and Data Definitions* (FY 2025-26 edition):

1. For each metric and governing board, ``D`` is the average of the four most recent
   years divided by the average of the three oldest of those four years.
2. ``D`` is multiplied by the board's share of total state funding in the previous
   fiscal year (the "role and mission adjusted share").
3. Each board's allocation for the metric is its adjusted share divided by the total
   adjusted share across boards.
4. The weighted sum of the eight metric allocations is the board's Step 2 share.

Source: https://cdhe.colorado.gov/sites/highered/files/Colorado_Performance_Funding_Overview_and_Data_Definitions_2025_26_1.pdf

The functions here are pure and data-source agnostic. Which data feed each metric
(SURDS, IPEDS, or CDHE's FTE collection), and how faithfully IPEDS can stand in for
the state's own records, is documented in ``METRICS`` and handled in notebook 11.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

# Step 2 weights under HB 20-1366, FY 2021-22 onward. HB 26-1345 replaces the model
# from FY 2027-28, so these weights describe FY 2021-22 to FY 2026-27 only.
WEIGHTS: dict[str, float] = {
    "resident_fte": 0.10,
    "first_gen": 0.05,
    "credentials": 0.05,
    "pell_share": 0.20,
    "urm_share": 0.20,
    "retention": 0.20,
    "grad100": 0.10,
    "grad150": 0.10,
}

# What CDHE uses for each metric, what IPEDS offers instead, and how close it is.
METRICS: dict[str, dict[str, str]] = {
    "resident_fte": {
        "label": "Resident FTE enrollment",
        "cdhe": "CDHE aggregate FTE collection, resident instruction FTE",
        "proxy": "Same CDHE series (hed1540), read from dashboard/data/colorado.json",
        "fidelity": "same source",
    },
    "first_gen": {
        "label": "Resident first-generation UG headcount",
        "cdhe": "SURDS enrollment file, FirstGeneration = 1, residents, fall",
        "proxy": "None: IPEDS does not collect first-generation status",
        "fidelity": "not available (held neutral)",
    },
    "credentials": {
        "label": "Resident credential completion",
        "cdhe": "SURDS degree file, resident awards plus qualifying transfers, all weighted 1",
        "proxy": "IPEDS C_A, CIP 99 first-major totals; all students, no transfers",
        "fidelity": "proxy",
    },
    "pell_share": {
        "label": "Resident Pell-eligible share",
        "cdhe": "SURDS, residents with 9-month EFC at or below the Pell threshold / resident headcount",
        "proxy": "IPEDS SFA UPGRNTN / SCUGRAD: Pell recipients among all undergraduates",
        "fidelity": "proxy",
    },
    "urm_share": {
        "label": "Resident underrepresented minority share",
        "cdhe": "SURDS, resident Black + Hispanic + Native American / resident U.S. headcount",
        "proxy": "IPEDS EF_A (EFALEVEL 1): Black + Hispanic + AIAN / (total - nonresident)",
        "fidelity": "proxy",
    },
    "retention": {
        "label": "Retention rate",
        "cdhe": "IPEDS EF_D for four-year and most two-year colleges; SURDS for eight CCCS colleges",
        "proxy": "IPEDS EF_D RET_NMF / RRFTCTA",
        "fidelity": "same source (except eight CCCS colleges)",
    },
    "grad100": {
        "label": "100% graduation rate",
        "cdhe": "IPEDS GR (bachelor's subcohort or 2-year cohort); SURDS for eight CCCS colleges",
        "proxy": "IPEDS GR GRTYPE 13/8 (4-year) or 35/29 (2-year)",
        "fidelity": "same source (except eight CCCS colleges)",
    },
    "grad150": {
        "label": "150% graduation rate",
        "cdhe": "IPEDS GR (bachelor's subcohort or 2-year cohort); SURDS for eight CCCS colleges",
        "proxy": "IPEDS GR GRTYPE 12/8 (4-year) or 30/29 (2-year)",
        "fidelity": "same source (except eight CCCS colleges)",
    },
}


def d_ratio(values: Iterable[float]) -> float:
    """Four-year average divided by the average of its three oldest years.

    ``values`` are the four window years, oldest first. Returns NaN unless exactly
    four non-missing values are supplied, so a gap in the window cannot pass as a
    ratio computed on fewer years.

    Algebraically ``D = 0.75 + 0.25 * x4 / mean(x1, x2, x3)``: only the newest year
    moves ``D``, and only a quarter as much as its change relative to the prior mean.
    """
    v = np.asarray(list(values), dtype=float)
    if v.shape != (4,) or np.isnan(v).any():
        return float("nan")
    return float(v.mean() / v[:3].mean())


def metric_allocation(prior_share: pd.Series, d: pd.Series) -> pd.Series:
    """One metric's allocation shares: ``A * D`` normalised to sum to one."""
    if d.isna().any():
        missing = sorted(d.index[d.isna()].astype(str))
        raise ValueError(f"D is missing for {missing}; refusing to allocate on a partial set")
    adjusted = prior_share.reindex(d.index) * d
    return adjusted / adjusted.sum()


def step2_shares(
    prior_share: pd.Series, d: pd.DataFrame, weights: dict[str, float] | None = None
) -> pd.Series:
    """Weighted Step 2 shares by board.

    ``prior_share`` is each board's share of prior-year funding; ``d`` holds one column
    of ``D`` ratios per metric. A metric absent from ``d`` is treated as neutral: its
    allocation equals the prior share, which is what the formula produces when every
    board has the same ``D``. The result sums to one.
    """
    weights = WEIGHTS if weights is None else weights
    if not np.isclose(sum(weights.values()), 1.0):
        raise ValueError(f"weights sum to {sum(weights.values()):.4f}, not 1")
    base = prior_share / prior_share.sum()
    total = pd.Series(0.0, index=base.index)
    for metric, weight in weights.items():
        alloc = metric_allocation(base, d[metric]) if metric in d else base
        total = total + weight * alloc
    return total


def formula_window(fiscal_year_start: int, metric: str) -> list[int]:
    """Data years CDHE uses for the formula year starting July ``fiscal_year_start``.

    Years follow IPEDS file labels: fall ``y`` for EF and SFA-derived fall measures,
    the ``GR{y}`` release for graduation rates, and the ``C{y}_A`` award year (July
    ``y-1`` to June ``y``) for credentials. For FY 2024-25 CDHE documents fall 2019 to
    fall 2022 enrollment, retention from EF2019D to EF2022D, and graduation cohorts
    that end in the GR2022 release; credentials run through award year 2022-23.
    """
    t = fiscal_year_start
    if metric == "credentials":
        return list(range(t - 4, t))
    if metric not in WEIGHTS:
        raise KeyError(f"unknown metric {metric!r}")
    return list(range(t - 5, t - 1))


def fiscal_year_label(start: int) -> str:
    """``2025`` -> ``"FY 2025-26"``, the label used in dashboard/data/colorado.json."""
    return f"FY {start}-{str(start + 1)[2:]}"


def consistent_reporters(panel: pd.DataFrame, years: list[int]) -> pd.Index:
    """Institutions observed under one definition in every window year.

    ``panel`` has ``UNITID``, ``year``, ``num``, ``den`` and optionally ``src`` (the
    cohort definition). An institution is kept only if every window year has a
    numerator, a positive denominator (when one applies), and the same ``src``. This
    removes the CCCS colleges whose IPEDS cohort changes definition or drops to zero
    when IPEDS reclassifies them as four-year.
    """
    window = panel[panel["year"].isin(years)]
    src = window["src"] if "src" in window else pd.Series("", index=window.index)
    valid = window["num"].notna() & (window["den"].isna() | (window["den"] > 0))
    summary = pd.DataFrame(
        {"UNITID": window["UNITID"], "year": window["year"], "valid": valid, "src": src}
    )
    agg = summary.groupby("UNITID").agg(
        years=("year", "nunique"),
        valid=("valid", "all"),
        definitions=("src", lambda s: s.nunique(dropna=False)),
    )
    keep = (agg["years"] == len(years)) & agg["valid"] & (agg["definitions"] == 1)
    return agg.index[keep]


def board_series(panel: pd.DataFrame, years: list[int], *, how: str = "pooled") -> pd.DataFrame:
    """Board-by-year values for one metric from consistent reporters.

    ``how="pooled"`` sums numerators and denominators across a board's institutions
    (counts are summed when there is no denominator); ``how="mean"`` averages
    institution rates. CDHE says metrics are "summed to the governing board level"
    but does not say which applies to rates, so the notebook reports both.
    """
    if how not in {"pooled", "mean"}:
        raise ValueError("how must be 'pooled' or 'mean'")
    keep = consistent_reporters(panel, years)
    d = panel[panel["UNITID"].isin(keep) & panel["year"].isin(years)]
    if d["den"].isna().all():
        values = d.groupby(["board", "year"])["num"].sum()
    elif how == "pooled":
        sums = d.groupby(["board", "year"])[["num", "den"]].sum()
        values = sums["num"] / sums["den"]
    else:
        values = (d["num"] / d["den"]).groupby([d["board"], d["year"]]).mean()
    return values.unstack("year").reindex(columns=years)


def redistribution(base: pd.Series, new: pd.Series) -> pd.DataFrame:
    """Compare actual allocations with a uniform increase of the same total.

    Returns each board's actual change, the change under a uniform percentage
    increase, and the difference: the money the formula moved between boards.
    """
    uniform = base * new.sum() / base.sum()
    return pd.DataFrame(
        {
            "base": base,
            "actual": new,
            "uniform": uniform,
            "moved": new - uniform,
            "actual_pct": (new / base - 1) * 100,
        }
    )
