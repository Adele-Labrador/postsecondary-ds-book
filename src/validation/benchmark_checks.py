"""Compare model-derived metrics to independently published figures.

Every check cites the ground-truth source it expects the caller to have
sourced (institution's IPEDS Data Feedback Report, NCES Digest of Education
Statistics tables, Carnegie Classification labels, or a peer-reviewed
replication target), per the NCES Statistical Standards' guidance on
transparent, well-documented comparisons
(https://nces.ed.gov/pubs2003/2003601.pdf). This module never fabricates a
benchmark -- callers must supply the published values themselves.
"""

from __future__ import annotations

import pandas as pd


def compare_to_published(
    model_df: pd.DataFrame,
    published_df: pd.DataFrame,
    value_col: str,
    key_cols: tuple[str, ...] = ("unitid", "survey_year"),
    tolerance: float = 0.02,
) -> pd.DataFrame:
    """Generic benchmark comparison: merges model output to a published
    reference table on ``key_cols`` and flags rows within ``tolerance``
    absolute difference.
    """
    merged = model_df.merge(published_df, on=list(key_cols), suffixes=("_model", "_published"))
    model_col = f"{value_col}_model"
    published_col = f"{value_col}_published"
    if model_col not in merged.columns or published_col not in merged.columns:
        raise ValueError(
            f"Expected columns '{model_col}' and '{published_col}' after merge; "
            f"got {list(merged.columns)}"
        )
    merged["abs_diff"] = (merged[model_col] - merged[published_col]).abs()
    merged["within_tolerance"] = merged["abs_diff"] <= tolerance
    return merged


def classification_agreement(predicted: pd.Series, ground_truth: pd.Series) -> float:
    """Share of predictions matching an independent ground-truth label
    (e.g. predicted vs. official Carnegie Classification).
    """
    if len(predicted) != len(ground_truth):
        raise ValueError("predicted and ground_truth must be the same length")
    aligned = pd.DataFrame({"pred": predicted.values, "truth": ground_truth.values})
    return float((aligned["pred"] == aligned["truth"]).mean())


def summarize_benchmark(comparison: pd.DataFrame) -> dict:
    """Small summary dict for reporting in a chapter notebook."""
    return {
        "n_compared": len(comparison),
        "mean_abs_diff": float(comparison["abs_diff"].mean()),
        "pct_within_tolerance": float(comparison["within_tolerance"].mean()),
    }
