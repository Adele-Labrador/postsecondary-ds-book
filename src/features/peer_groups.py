"""Peer-group construction, anchored to the Carnegie Classification of
Institutions of Higher Education (https://carnegieclassifications.acenet.edu/).

Carnegie is the field's accepted taxonomy for institutional type, so any
"classify institution type" chapter should validate against it rather than
an ad hoc rule -- see the book's Section 6 (validation against established
research standards).
"""

from __future__ import annotations

import pandas as pd


def attach_carnegie_classification(
    institutions: pd.DataFrame, carnegie: pd.DataFrame
) -> pd.DataFrame:
    """Left-join an institution table onto the Carnegie Classification file.

    ``carnegie`` is expected to have one row per ``unitid`` with a
    ``carnegie_basic`` label (the "Basic Classification" category, e.g.
    "Doctoral Universities: Very High Research Activity") -- Carnegie
    publishes a fresh classification periodically rather than annually, so
    it is joined on ``unitid`` alone, not ``unitid`` + ``survey_year``.
    """
    required = {"unitid", "carnegie_basic"}
    missing = required - set(carnegie.columns)
    if missing:
        raise ValueError(f"Carnegie file missing required columns: {missing}")

    return institutions.merge(carnegie[["unitid", "carnegie_basic"]], on="unitid", how="left")


def build_peer_group(
    panel: pd.DataFrame,
    target_unitid: int,
    year: int,
    group_cols: list[str] | None = None,
    size_tolerance: float = 0.25,
) -> pd.DataFrame:
    """Return other institutions that share classification/control/level
    with ``target_unitid`` in ``year``, and fall within +/- ``size_tolerance``
    of its enrollment -- a simple, transparent peer-group rule readers can
    audit and adjust, in the same spirit as an IPEDS Data Feedback Report
    comparison group.
    """
    group_cols = group_cols or ["carnegie_basic", "control", "level"]
    missing = set(group_cols + ["unitid", "survey_year", "total_enrollment"]) - set(panel.columns)
    if missing:
        raise ValueError(f"panel is missing required columns: {sorted(missing)}")

    year_slice = panel[panel["survey_year"] == year]
    target_rows = year_slice[year_slice["unitid"] == target_unitid]
    if target_rows.empty:
        raise ValueError(f"unitid {target_unitid} not found in panel for {year}")
    target = target_rows.iloc[0]

    same_group = year_slice
    for col in group_cols:
        same_group = same_group[same_group[col] == target[col]]

    low = target["total_enrollment"] * (1 - size_tolerance)
    high = target["total_enrollment"] * (1 + size_tolerance)
    peers = same_group[
        (same_group["total_enrollment"] >= low)
        & (same_group["total_enrollment"] <= high)
        & (same_group["unitid"] != target_unitid)
    ]
    return peers
