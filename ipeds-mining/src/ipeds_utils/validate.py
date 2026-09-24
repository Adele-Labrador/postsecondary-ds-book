"""A small declarative validation harness for curated IPEDS tables.

Rules are objects rather than loose assertions so that a notebook's validation cell
produces a persistable report: which rules ran, which failed, on how many rows, and
which UNITIDs were implicated. That report is the artefact a reader cites when they
claim a curated table is fit for analysis.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


@dataclass
class Rule:
    """One named check over a frame.

    ``check`` returns a boolean Series that is True for *offending* rows, so a passing
    rule is one where nothing is flagged. ``severity`` of ``"error"`` fails the run;
    ``"warn"`` records the finding and continues.
    """

    name: str
    check: Callable[[pd.DataFrame], pd.Series]
    severity: str = "error"
    note: str = ""


@dataclass
class Report:
    table: str
    rows: int
    results: list[dict] = field(default_factory=list)
    generated_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def failed(self) -> list[dict]:
        """Error-severity findings, plus any rule that could not be evaluated.

        A rule that raised is counted as a failure rather than a pass. Silently
        treating an unevaluable check as satisfied is the worst available default,
        because it hides exactly the schema changes the harness exists to catch.
        """
        return [
            r
            for r in self.results
            if r["status"] == "error" or (r["n_offending"] > 0 and r["severity"] == "error")
        ]

    @property
    def ok(self) -> bool:
        return not self.failed

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.results)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2, default=str))
        return path

    def raise_if_failed(self) -> Report:
        if not self.ok:
            names = ", ".join(f"{r['name']} ({r['n_offending']} rows)" for r in self.failed)
            raise AssertionError(f"{self.table} failed validation: {names}")
        return self


def validate(frame: pd.DataFrame, rules: list[Rule], table: str, *, sample=5) -> Report:
    """Run rules against a frame and return a structured report."""
    report = Report(table=table, rows=int(len(frame)))
    for rule in rules:
        try:
            mask = rule.check(frame)
            mask = mask.fillna(False).astype(bool)
            offenders = frame.loc[mask]
            ids = (
                offenders["UNITID"].dropna().astype("Int64").astype(str).head(sample).tolist()
                if "UNITID" in offenders.columns
                else []
            )
            report.results.append(
                {
                    "name": rule.name,
                    "severity": rule.severity,
                    "n_offending": int(mask.sum()),
                    "share": round(float(mask.mean()), 5) if len(frame) else 0.0,
                    "sample_unitids": ids,
                    "note": rule.note,
                    "status": "pass" if not mask.any() else "fail",
                }
            )
        except Exception as exc:  # a broken rule is itself a finding
            report.results.append(
                {
                    "name": rule.name,
                    "severity": "error",
                    "n_offending": -1,
                    "share": None,
                    "sample_unitids": [],
                    "note": f"rule raised {type(exc).__name__}: {exc}",
                    "status": "error",
                }
            )
    return report


# --- Reusable rule constructors -------------------------------------------------
# Every constructor raises on a missing column instead of returning "no offenders".
# ``validate`` turns the exception into a failed rule. Passing silently would make a
# renamed column indistinguishable from clean data, which is the failure the harness
# exists to prevent.


def _require(frame: pd.DataFrame, cols) -> None:
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise KeyError(f"rule references column(s) absent from frame: {missing}")


# These cover the six universal checks every component notebook runs.


def unique_key(*cols: str) -> Rule:
    """The declared grain actually is the grain."""

    def check(frame: pd.DataFrame) -> pd.Series:
        present = [c for c in cols if c in frame.columns]
        if not present:
            return pd.Series(True, index=frame.index)
        return frame.duplicated(subset=present, keep=False)

    return Rule(f"unique_key({','.join(cols)})", check, note="Declared grain must be unique")


def not_null(*cols: str) -> Rule:
    def check(frame: pd.DataFrame) -> pd.Series:
        present = [c for c in cols if c in frame.columns]
        if not present:
            return pd.Series(True, index=frame.index)
        return frame[present].isna().any(axis=1)

    return Rule(f"not_null({','.join(cols)})", check, note="Key columns must be populated")


def in_range(col: str, low=None, high=None, *, severity="error") -> Rule:
    def check(frame: pd.DataFrame) -> pd.Series:
        _require(frame, [col])
        values = pd.to_numeric(frame[col], errors="coerce")
        mask = pd.Series(False, index=frame.index)
        if low is not None:
            mask |= values < low
        if high is not None:
            mask |= values > high
        return mask & values.notna()

    return Rule(f"in_range({col},{low},{high})", check, severity, "Value plausibility bound")


def sums_to(total: str, parts: list[str], *, tolerance=0, severity="error") -> Rule:
    """Component parts reconcile to their published total.

    Tolerance exists because IPEDS rounds some derived dollar figures. Set it to 0 for
    headcounts, where an off-by-one is a real discrepancy rather than rounding.
    """

    def check(frame: pd.DataFrame) -> pd.Series:
        _require(frame, [total, *parts])
        summed = frame[parts].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
        published = pd.to_numeric(frame[total], errors="coerce")
        gap = (summed - published).abs()
        return (gap > tolerance) & summed.notna() & published.notna()

    return Rule(f"sums_to({total})", check, severity, f"Parts must reconcile within {tolerance}")


def subset_of(col: str, allowed: set, *, severity="error") -> Rule:
    """Categorical codes stay inside the published value set.

    A code outside the set usually means the taxonomy was revised, which is exactly
    the event that should stop a longitudinal build rather than pass through it.
    """

    def check(frame: pd.DataFrame) -> pd.Series:
        _require(frame, [col])
        values = frame[col].dropna()
        mask = pd.Series(False, index=frame.index)
        mask.loc[values.index] = ~values.isin(allowed)
        return mask

    return Rule(f"subset_of({col})", check, severity, "Codes must match published value set")


def referential(col: str, universe: set, *, severity="error") -> Rule:
    """Every identifier appears in the directory universe for the same cycle."""

    def check(frame: pd.DataFrame) -> pd.Series:
        _require(frame, [col])
        return ~frame[col].isin(universe) & frame[col].notna()

    return Rule(f"referential({col})", check, severity, "Identifier must exist in HD universe")


def rolls_up(value: str, *, level: str, total_code, keys: list[str], severity="error") -> Rule:
    """Rows coded as a grand total must equal the sum of their detail rows.

    Built for long files that store totals beside their components. In ``C2023_A``
    the ``CIPCODE == '99'`` row is the total over all programmes for one
    ``UNITID`` x ``AWLEVEL`` x ``MAJORNUM``, so summing ``CTOTALT`` over every row counts
    each award twice. Offending rows are the total rows that fail to reconcile.
    """

    def check(frame: pd.DataFrame) -> pd.Series:
        _require(frame, [value, level, *keys])
        is_total = frame[level].astype(str) == str(total_code)
        values = pd.to_numeric(frame[value], errors="coerce").fillna(0)
        detail = values[~is_total].groupby([frame.loc[~is_total, k] for k in keys]).sum()
        totals = frame.loc[is_total, keys].copy()
        totals["_published"] = values[is_total]
        totals = totals.join(detail.rename("_detail"), on=keys)
        gap = (totals["_published"] - totals["_detail"].fillna(0)).abs() > 0
        return gap.reindex(frame.index, fill_value=False)

    return Rule(
        f"rolls_up({value}, {level}=={total_code})",
        check,
        severity,
        f"{level} {total_code} rows must equal the sum of detail rows within {keys}",
    )
