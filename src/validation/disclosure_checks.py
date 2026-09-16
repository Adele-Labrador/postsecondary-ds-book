"""Disclosure-safety checks enforcing NCES minimum-cell-size conventions.

The NCES Statistical Standards require suppressing or masking small-N cells
to protect individual privacy (https://nces.ed.gov/pubs2003/2003601.pdf).
Any chapter that reports subgroup breakdowns (e.g. by Pell status, race,
program) must run these checks before publishing a table or chart, not just
note the rule in prose.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_MIN_N = 10


def flag_small_cells(df: pd.DataFrame, count_col: str, min_n: int = DEFAULT_MIN_N) -> pd.DataFrame:
    """Add a boolean ``suppress`` column marking rows below the minimum
    reportable cell size.
    """
    out = df.copy()
    out["suppress"] = out[count_col] < min_n
    return out


def apply_suppression(
    df: pd.DataFrame,
    count_col: str,
    value_cols: list[str],
    min_n: int = DEFAULT_MIN_N,
    mask_value=None,
) -> pd.DataFrame:
    """Replace values in ``value_cols`` with ``mask_value`` wherever
    ``count_col`` falls below ``min_n``, mirroring how NCES masks published
    tables rather than dropping rows outright.
    """
    out = flag_small_cells(df, count_col, min_n)
    out.loc[out["suppress"], value_cols] = mask_value
    return out


def suppression_rate(df: pd.DataFrame, count_col: str, min_n: int = DEFAULT_MIN_N) -> float:
    """Share of rows that would be suppressed -- useful as a chapter-level
    sanity metric (a very high rate may mean the analysis is sliced too
    finely for the underlying institution-level data).
    """
    flagged = flag_small_cells(df, count_col, min_n)
    return float(flagged["suppress"].mean())
