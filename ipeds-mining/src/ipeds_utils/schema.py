"""CSV loading, schema locking, and imputation-flag handling."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .dictionary import imputation_partner
from .fetch import unzip_csv

# Encoding is not uniform across the IPEDS distribution. Most files are UTF-8, many
# carry a byte-order mark on the header row, and some older or Latin-1 files fail UTF-8
# decoding outright on accented institution names. Candidates are tried in order:
# utf-8-sig strips a BOM when present and is otherwise identical to utf-8; cp1252 is
# the fallback that always decodes.
IPEDS_ENCODINGS = ("utf-8-sig", "cp1252")
IPEDS_ENCODING = IPEDS_ENCODINGS[0]  # retained for backwards compatibility

# Identifier-like codes that must stay text. Parsed as numbers they lose information
# silently: CIP 13.0100 becomes 13.01 and 01.0000 becomes 1.0, which breaks joins to the
# CIP taxonomy and 2-digit family grouping; OPEID and ZIP lose leading zeros.
STRING_CODES = ("CIPCODE", "OPEID", "ZIP", "EIN", "UEIS", "F1SYSCOD")

# The derived (DRV*) files, and some component files, mark missing numeric cells with a
# lone "." (a SAS convention) instead of leaving them blank. Unhandled, one dot turns the
# whole column into text; coerced with errors="coerce", it silently becomes NaN with no
# record that the value was missing by design. Declaring it here makes it explicit.
MISSING_MARKERS = (".",)

# Zero-width and BOM characters that leak into the first column name.
_INVISIBLES = "\ufeff\u200b\u200e\u200f"


def _clean(name) -> str:
    """Normalise a raw column name: strip BOM, whitespace, and case."""
    return str(name).strip(_INVISIBLES).strip().upper()


def _read_with_fallback(payload: bytes, **kwargs) -> pd.DataFrame:
    """Parse CSV bytes, trying each candidate encoding in turn."""
    import io as _io

    last: Exception | None = None
    for encoding in IPEDS_ENCODINGS:
        try:
            return pd.read_csv(_io.BytesIO(payload), encoding=encoding, **kwargs)
        except UnicodeDecodeError as exc:
            last = exc
    raise UnicodeDecodeError(*last.args) if last else RuntimeError("unreachable")


def read_csv(zip_path: str | Path, usecols=None, *, dtype=None) -> pd.DataFrame:
    """Read the CSV inside an IPEDS archive with correct encoding and UNITID typing.

    Column selection is case-insensitive. This matters more than it sounds: the data
    files ship lowercase headers (``unitid``, ``instnm``) while the dictionaries and
    all NCES documentation use uppercase (``UNITID``, ``INSTNM``), and the convention
    is not consistent across cycles. Passing dictionary-cased names to a naive reader
    raises "Usecols do not match columns". Column names are normalised to uppercase on
    the way out, so all downstream code can assume uppercase.

    Identifier-like code columns in ``STRING_CODES`` (``CIPCODE``, ``OPEID``, ``ZIP``)
    are always read as text; see the note on that constant.

    A lone ``.`` is read as missing (see ``MISSING_MARKERS``).

    ``UNITID`` is always read as a nullable integer. It is a stable NCES identifier,
    never arithmetic, and letting pandas infer it as float introduces ``.0`` suffixes
    that break joins in confusing ways.
    """
    payload, member = unzip_csv(zip_path)
    header = _read_with_fallback(payload, nrows=0)
    raw_by_clean = {_clean(c): c for c in header.columns}

    selector = None
    if usecols is not None:
        wanted = {_clean(c) for c in usecols}
        missing = sorted(wanted - set(raw_by_clean))
        if missing:
            raise KeyError(
                f"{Path(zip_path).name} has no column(s) {missing}. Check the "
                "dictionary varlist; IPEDS renames columns between collection cycles."
            )
        selector = lambda c: _clean(c) in wanted  # noqa: E731

    # Code columns are always text. Keys are mapped back to the raw header spelling,
    # because pandas matches dtype keys against the header exactly as written.
    requested = {
        **{c: str for c in STRING_CODES},
        **{_clean(k): v for k, v in (dtype or {}).items()},
    }
    dtype = {raw_by_clean[k]: v for k, v in requested.items() if k in raw_by_clean}

    frame = _read_with_fallback(
        payload, usecols=selector, dtype=dtype, na_values=MISSING_MARKERS, low_memory=False
    )
    frame.columns = [_clean(c) for c in frame.columns]
    for code in STRING_CODES:
        if code in frame.columns:
            frame[code] = frame[code].str.strip()  # OPEID ships right-padded
    if "UNITID" in frame.columns:
        frame["UNITID"] = pd.to_numeric(frame["UNITID"], errors="coerce").astype("Int64")
    frame.attrs["source_member"] = member
    frame.attrs["source_archive"] = str(zip_path)
    return frame


def lock_schema(frame: pd.DataFrame, table: str, schema_dir="schemas", *, strict=True) -> dict:
    """Record or verify the column signature of a table.

    On first run this writes ``schemas/<table>.json``. On every later run it compares
    the current columns against that record and reports what changed.

    This is the mechanism that makes a multi-year notebook trustworthy. IPEDS revises
    its column sets between cycles, and an unnoticed rename turns a longitudinal trend
    into an artefact of the file format. With ``strict=True`` a change is an exception
    the reader must consciously resolve, not a warning they scroll past.

    Returns
    -------
    dict
        ``{"status": "created"|"unchanged"|"changed", "added": [...], "removed": [...]}``
    """
    schema_dir = Path(schema_dir)
    schema_dir.mkdir(parents=True, exist_ok=True)
    path = schema_dir / f"{table}.json"
    current = sorted(frame.columns)

    if not path.exists():
        path.write_text(json.dumps({"table": table, "columns": current}, indent=2))
        return {"status": "created", "added": [], "removed": [], "path": str(path)}

    recorded = sorted(json.loads(path.read_text())["columns"])
    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    if not added and not removed:
        return {"status": "unchanged", "added": [], "removed": [], "path": str(path)}

    message = (
        f"Schema drift in {table}: {len(added)} added {added[:8]}, "
        f"{len(removed)} removed {removed[:8]}. "
        f"Resolve deliberately, then delete {path} to re-lock."
    )
    if strict:
        raise ValueError(message)
    print(f"WARNING: {message}")
    return {"status": "changed", "added": added, "removed": removed, "path": str(path)}


def split_imputation_flags(
    frame: pd.DataFrame, value_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate reported values from their ``X``-prefixed imputation flags.

    Returns ``(values, flags)`` where ``flags`` is reindexed to match ``values`` so the
    two can be carried together. Any value column without a flag present in the file
    is simply absent from ``flags`` rather than fabricated.
    """
    keys = [c for c in ("UNITID",) if c in frame.columns]
    present = [c for c in value_cols if c in frame.columns]
    flag_map = {c: imputation_partner(c) for c in present}
    flag_cols = [f for f in flag_map.values() if f in frame.columns]
    return frame[keys + present].copy(), frame[keys + flag_cols].copy()


def imputation_summary(flags: pd.DataFrame) -> pd.DataFrame:
    """Tabulate imputation-flag codes per column as shares of all records.

    A column where a large share of institutions carry a generated or imputed flag
    should not be modelled as if it were observed. This table is what makes that
    judgement possible before the modelling starts rather than after.
    """
    rows = []
    for col in flags.columns:
        if col == "UNITID":
            continue
        counts = flags[col].astype("string").fillna("(missing)").value_counts()
        total = int(counts.sum())
        for code, count in counts.items():
            rows.append(
                {"column": col, "flag": code, "n": int(count), "share": round(count / total, 4)}
            )
    return pd.DataFrame(rows).sort_values(["column", "n"], ascending=[True, False])


def decode(frame: pd.DataFrame, valuesets: pd.DataFrame, column: str, *, into=None) -> pd.DataFrame:
    """Attach official labels for a categorical column from the dictionary value sets.

    Decoding from the published value set rather than a hand-written dictionary means
    a taxonomy revision shows up as unmatched codes, which ``validate`` can catch,
    instead of as a plausible-looking wrong label.
    """
    into = into or f"{column}_LABEL"
    if valuesets.empty:
        frame[into] = pd.NA
        return frame
    cols = {c.lower(): c for c in valuesets.columns}
    var_col = cols.get("varname") or cols.get("varnumber")
    code_col = cols.get("codevalue") or cols.get("code")
    label_col = cols.get("valuelabel") or cols.get("label")
    if not all([var_col, code_col, label_col]):
        frame[into] = pd.NA
        return frame
    subset = valuesets[
        valuesets[var_col].astype("string").str.strip().str.upper() == column.upper()
    ]
    mapping = dict(
        zip(
            code_key(subset[code_col]),
            subset[label_col].astype("string").str.strip(),
        )
    )
    frame[into] = code_key(frame[column]).map(mapping)
    return frame


def code_key(series: pd.Series) -> pd.Series:
    """Canonical text form of a categorical code, for matching against value sets.

    Masking a reserved code (-3) to NaN silently converts an integer column to float,
    after which ``SECTOR == 1`` is stored as ``1.0`` and no longer matches the value
    set's ``"1"``. Integral numbers are therefore rendered without a decimal part.
    Codes that are not purely numeric (CIP codes such as ``"01.0000"``) are left as
    written, because their zeros are significant.
    """
    text = series.astype("string").str.strip()
    # Only the shapes a float rendering produces: "3" or "3.0". "10.0000" is a CIP code.
    float_like = text.str.fullmatch(r"-?[1-9]\d*(\.0)?|-?0(\.0)?", na=False)
    as_int = pd.to_numeric(text.where(float_like), errors="coerce").astype("Int64").astype("string")
    return text.where(~float_like, as_int)
