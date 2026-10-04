"""Small-cell suppression and identifier pseudonymisation.

A clarification that matters pedagogically: IPEDS institution-level files are already
public and contain no individual records, so nothing here is protecting student
privacy in the raw data. Two other risks are real, and these tools address those:

1. **Re-identification of institutions in derived products.** A cross-tabulation of a
   small institution's completions by program by demographic group can isolate one or
   two students even though each input file was aggregate. Suppression addresses this.
2. **Teaching correct habits on data where mistakes are cheap.** Readers who go on to
   work with restricted-use NCES files or their own registrar extracts need the
   suppression-and-pseudonymisation workflow to be reflex. Practising it here is the
   point.

Suppression is therefore applied to *derived* cross-tabulations, not to raw curated
tables, and pseudonymisation is offered for classroom distribution rather than
presented as a requirement for public IPEDS data.
"""

from __future__ import annotations

import hashlib
import hmac

import pandas as pd

SUPPRESSED = pd.NA


def suppress(
    frame: pd.DataFrame,
    count_cols: list[str],
    *,
    threshold: int = 10,
    complementary: bool = True,
    group_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Blank cells below a reporting threshold, with complementary suppression.

    Primary suppression alone leaks: if a total is published and every category but one
    is suppressed, the remaining value is recoverable by subtraction. When
    ``complementary=True`` and ``group_cols`` is given, a second cell in any group with
    exactly one suppression is also blanked.

    Parameters
    ----------
    threshold
        Minimum publishable count. 10 is a common convention; the correct value comes
        from the governing policy, not from this default.
    group_cols
        Columns defining a group whose parts could be differenced against a total.

    Returns
    -------
    (frame, audit)
        ``frame`` is a copy with suppressed cells set to NA and an added
        ``_suppressed`` boolean column. ``audit`` records counts per column so the
        suppression itself is documented and reviewable.
    """
    absent = [c for c in [*count_cols, *(group_cols or [])] if c not in frame.columns]
    if absent:
        # Skipping an absent column would publish it unsuppressed or skip the
        # complementary step, and nothing downstream would notice.
        raise KeyError(f"suppression column(s) absent from frame: {absent}")
    out = frame.copy()
    mask = pd.DataFrame(False, index=out.index, columns=count_cols)
    unprotected = {c: 0 for c in count_cols}

    for col in count_cols:
        if col not in out.columns:
            continue
        values = pd.to_numeric(out[col], errors="coerce")
        primary = (values > 0) & (values < threshold)
        mask[col] = primary.fillna(False)

    if complementary and group_cols:
        present = [c for c in group_cols if c in out.columns]
        if present:
            for col in count_cols:
                if col not in out.columns:
                    continue
                values = pd.to_numeric(out[col], errors="coerce")
                grouper = present[0] if len(present) == 1 else present
                for _, idx in out.groupby(grouper, dropna=False).groups.items():
                    idx = pd.Index(idx)
                    if mask.loc[idx, col].sum() != 1:
                        continue
                    # Blank the smallest unsuppressed non-null cell as well.
                    candidates = values.loc[idx][~mask.loc[idx, col] & values.loc[idx].notna()]
                    if not candidates.empty:
                        mask.loc[candidates.idxmin(), col] = True
                    else:
                        # A one-cell group: the cell equals the group total, so no
                        # complement exists. Only suppressing the total protects it.
                        unprotected[col] += 1

    for col in count_cols:
        if col in out.columns:
            out.loc[mask[col], col] = SUPPRESSED

    out["_suppressed"] = mask.any(axis=1)
    audit = pd.DataFrame(
        {
            "column": count_cols,
            "n_suppressed": [int(mask[c].sum()) if c in mask else 0 for c in count_cols],
            "threshold": threshold,
            "groups_needing_total_suppressed": [unprotected[c] for c in count_cols],
        }
    )
    return out, audit


def synthetic_id(unitids: pd.Series, *, salt: str, prefix: str = "INST", keep_map: bool = False):
    """Map UNITIDs to stable pseudonyms using a keyed HMAC.

    A plain hash of a UNITID is trivially reversible: there are roughly six thousand
    institutions, so an adversary hashes the whole list and inverts the mapping in
    seconds. A secret salt under HMAC is what makes the pseudonym meaningful, and the
    salt must not be committed alongside the data it protects.

    The mapping is deterministic for a fixed salt, so pseudonyms remain joinable
    across years and across notebooks.

    Returns
    -------
    Series, or (Series, DataFrame)
        The pseudonym series, plus the crosswalk when ``keep_map=True``. Store any
        crosswalk outside the distributed dataset.
    """
    if not salt or salt in {"changeme", "salt", ""}:
        raise ValueError(
            "Refusing to pseudonymise with a placeholder salt. Supply a secret salt "
            "from the environment, e.g. os.environ['IPEDS_SALT']."
        )

    def token(value) -> object:
        if pd.isna(value):
            return pd.NA
        digest = hmac.new(salt.encode(), str(int(value)).encode(), hashlib.sha256).hexdigest()
        return f"{prefix}_{digest[:12]}"

    pseudonyms = unitids.map(token)
    if not keep_map:
        return pseudonyms
    crosswalk = pd.DataFrame({"UNITID": unitids, "synthetic_id": pseudonyms}).drop_duplicates()
    return pseudonyms, crosswalk


def coarsen(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    """Bin a quasi-identifier into ranges.

    Enrolment size and endowment per student are effectively institution fingerprints
    at full precision. Binning them preserves analytic usefulness for clustering and
    benchmarking while removing the exact value that makes lookup trivial.
    """
    return pd.cut(pd.to_numeric(series, errors="coerce"), bins=bins, labels=labels, right=False)


def k_anonymity(frame: pd.DataFrame, quasi_identifiers: list[str]) -> pd.DataFrame:
    """Report the smallest equivalence-class size for a set of quasi-identifiers.

    If the minimum group size is 1, some row is unique on those columns and is
    re-identifiable regardless of whether its label was removed. Run this before
    releasing any derived table, and coarsen until the minimum reaches the target k.
    """
    missing = [c for c in quasi_identifiers if c not in frame.columns]
    if missing:
        # Dropping an absent quasi-identifier would understate risk: fewer columns
        # means larger equivalence classes and a falsely reassuring minimum k.
        raise KeyError(f"quasi-identifier(s) absent from frame: {missing}")
    present = list(quasi_identifiers)
    sizes = frame.groupby(present, dropna=False, observed=True).size().rename("class_size")
    return (
        sizes.reset_index()
        .assign(
            k=lambda d: d["class_size"],
            at_risk=lambda d: d["class_size"] == 1,
        )
        .sort_values("class_size")
    )
