"""Assemble the single wide institution-year feature store that every book
chapter notebook reads from ("one dataset, many models").

This module composes the standardized component tables (from
``src.ingest``) and the engineered feature tables (from
``src.features.ratios`` / ``peer_groups``) into one table keyed on
``unitid`` + ``survey_year``, then persists it to
``data/processed/panel.parquet``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_panel(
    institutional_characteristics: pd.DataFrame,
    student_faculty: pd.DataFrame | None = None,
    aid_intensity: pd.DataFrame | None = None,
    selectivity: pd.DataFrame | None = None,
    financial_health: pd.DataFrame | None = None,
    completion: pd.DataFrame | None = None,
    equity_gap: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Left-join every available feature table onto the institutional
    characteristics base table, on ``unitid`` + ``survey_year``.

    Any feature table may be omitted (``None``) -- the panel simply won't
    contain that block of columns, which lets partial pipelines (e.g. only
    ingested EF + HR so far) still produce a valid, smaller panel.
    """
    panel = institutional_characteristics.copy()
    optional_tables = [
        student_faculty,
        aid_intensity,
        selectivity,
        financial_health,
        completion,
        equity_gap,
    ]
    for table in optional_tables:
        if table is not None:
            panel = panel.merge(table, on=["unitid", "survey_year"], how="left")
    return panel


def save_panel(panel: pd.DataFrame, path: str = "data/processed/panel.parquet") -> Path:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out_path, index=False)
    return out_path


def load_panel(path: str = "data/processed/panel.parquet") -> pd.DataFrame:
    return pd.read_parquet(path)


if __name__ == "__main__":
    # `make data` entry point. In a real run this would call
    # src.ingest.* for each component/year first; kept minimal here since
    # the ingestion step depends on files the reader downloads themselves.
    print(
        "This is a scaffold entry point. Wire in calls to "
        "src.ingest.ipeds_complete_files.load_component(...) for each "
        "component/year, apply src.ingest.crosswalk, run the "
        "src.features.ratios / peer_groups functions, then call "
        "build_panel(...) and save_panel(...)."
    )
