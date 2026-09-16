"""Track ``unitid`` changes (mergers, closures, renamings) across IPEDS years.

Institutions occasionally close, merge, split, or get re-assigned a new
``unitid`` between IPEDS collection years. Left unhandled, this silently
breaks a multi-year institution-year panel (an institution's history appears
to "disappear" or duplicate). This module applies a small crosswalk table
so all rows in a panel resolve to one canonical ``unitid`` per institution.

Expected crosswalk schema (one row per historical change):

    unitid_from | unitid_to | effective_year | reason
    ------------|-----------|-----------------|-----------------
    100001      | 100050    | 2019            | merger
    100002      | 100002    | 2021            | closed
"""

from __future__ import annotations

import pandas as pd


def load_crosswalk(path: str) -> pd.DataFrame:
    cw = pd.read_csv(path)
    cw.columns = [c.strip().lower() for c in cw.columns]
    required = {"unitid_from", "unitid_to", "effective_year"}
    missing = required - set(cw.columns)
    if missing:
        raise ValueError(f"Crosswalk file missing required columns: {missing}")
    return cw


def apply_crosswalk(
    df: pd.DataFrame,
    crosswalk: pd.DataFrame,
    unitid_col: str = "unitid",
    year_col: str = "survey_year",
) -> pd.DataFrame:
    """Remap historical ``unitid`` values onto their canonical successor.

    Only remaps rows whose year is at or before the change's effective year,
    so pre-merger history rolls up to the surviving institution while rows
    already reported under the new id are left untouched.
    """
    out = df.copy()
    mapping = crosswalk.set_index("unitid_from")

    def resolve(row):
        uid = row[unitid_col]
        if uid in mapping.index:
            change = mapping.loc[uid]
            # Handle the (rare) case of multiple historical changes for one id.
            if isinstance(change, pd.DataFrame):
                change = (
                    change[change["effective_year"] >= row[year_col]].iloc[0]
                    if (change["effective_year"] >= row[year_col]).any()
                    else change.iloc[-1]
                )
            if row[year_col] <= change["effective_year"]:
                return change["unitid_to"]
        return uid

    out[unitid_col] = out.apply(resolve, axis=1).astype(int)
    return out


def flag_closed_institutions(crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Return the subset of crosswalk rows marking an institution as closed
    (``unitid_from == unitid_to`` and reason == 'closed'), useful for
    excluding closed institutions from forward-looking forecasts.
    """
    closed = crosswalk[
        (crosswalk["unitid_from"] == crosswalk["unitid_to"])
        & (crosswalk.get("reason", "").str.lower() == "closed")
    ]
    return closed[["unitid_from", "effective_year"]].rename(
        columns={"unitid_from": "unitid", "effective_year": "closed_year"}
    )
