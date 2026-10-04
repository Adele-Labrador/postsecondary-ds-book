"""Curated-table output with embedded metadata."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def curated_path(name: str, root: str | Path = "data/curated") -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{name}.parquet"


def write_curated(
    frame: pd.DataFrame,
    name: str,
    *,
    root: str | Path = "data/curated",
    reference_period: str,
    grain: list[str],
    provenance: list[dict] | None = None,
    notes: str = "",
) -> Path:
    """Write a curated table plus a sidecar metadata JSON.

    The sidecar carries the reference period and grain with the data. This is the
    defence against the single most common IPEDS error: assembling a panel by filename
    year when the underlying periods are offset differently per component. A consumer
    can read the sidecar and align on the declared period instead of guessing.
    """
    path = curated_path(name, root)
    frame.to_parquet(path, index=False)

    meta = {
        "name": name,
        "reference_period": reference_period,
        "grain": grain,
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "notes": notes,
        "provenance": provenance or [],
    }
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2, default=str))
    return path


def read_curated(name: str, root: str | Path = "data/curated") -> tuple[pd.DataFrame, dict]:
    """Read a curated table together with its metadata sidecar."""
    path = curated_path(name, root)
    meta_path = path.with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return pd.read_parquet(path), meta
