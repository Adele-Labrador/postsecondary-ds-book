"""Parsing of IPEDS Excel data dictionaries.

Three inconsistencies in the published dictionaries will crash or silently mislead a
naive reader, and all three are handled here:

1. **Sheet-name casing varies.** Most dictionaries expose ``varlist``, but some
   (notably ``EF2023C``) use ``Varlist``. Sheet lookup is case-insensitive.
2. **Header casing varies.** Most use ``varname``/``varTitle``; the Completions
   dictionaries (``C2023_A``, ``C2023_B``, ``C2023_C``) use ``varName``. All headers
   are normalised to lowercase before use.
3. **Embedded images are broken.** Loading without ``read_only=True`` raises
   ``KeyError: 'xl/drawings/NULL'`` on several files. ``read_only`` bypasses the
   drawing parser entirely and is therefore mandatory, not an optimisation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from .fetch import unzip_dict


def _open(source):
    """Open a dictionary from a zip path, an xlsx path, or a file-like object."""
    if hasattr(source, "read"):
        handle = source
    else:
        path = Path(source)
        handle = unzip_dict(path)[0] if path.suffix.lower() == ".zip" else path
    # read_only=True is required: it skips the drawing parser that raises
    # KeyError: 'xl/drawings/NULL' on dictionaries with broken embedded images.
    return load_workbook(handle, data_only=True, read_only=True)


def _sheet(workbook, wanted: str):
    for name in workbook.sheetnames:
        if name.strip().lower() == wanted.lower():
            return workbook[name]
    return None


def _sheet_frame(sheet) -> pd.DataFrame:
    rows = sheet.iter_rows(values_only=True)
    header = next(rows, None)
    if header is None:
        return pd.DataFrame()
    columns = [str(c).strip().lower() if c is not None else f"col{i}" for i, c in enumerate(header)]
    frame = pd.DataFrame(list(rows), columns=columns)
    return frame.dropna(how="all")


def read_dict(source) -> pd.DataFrame:
    """Return the variable list of an IPEDS dictionary as a tidy frame.

    The returned frame always has ``varname`` and ``vartitle`` columns, whatever the
    source file called them, plus whichever of ``datatype``, ``fieldwidth``,
    ``format``, and ``imputationvar`` the dictionary provided.

    Examples
    --------
    >>> variables = read_dict("data/raw/HD2023_Dict.zip")
    >>> variables.loc[variables.varname == "CONTROL", "vartitle"].item()
    'Control of institution'
    """
    workbook = _open(source)
    sheet = _sheet(workbook, "varlist")
    if sheet is None:
        raise ValueError(f"No varlist sheet found; available sheets: {workbook.sheetnames}")
    frame = _sheet_frame(sheet)
    frame = frame.rename(columns={"varnumber": "varnumber"})
    if "varname" not in frame.columns:
        raise ValueError(f"No varname column; found {list(frame.columns)}")
    frame["varname"] = frame["varname"].astype("string").str.strip()
    if "vartitle" in frame.columns:
        frame["vartitle"] = frame["vartitle"].astype("string").str.strip()
    return frame[frame["varname"].notna() & (frame["varname"] != "")].reset_index(drop=True)


def read_valuesets(source) -> pd.DataFrame:
    """Return the code/label value sets (the ``Frequencies`` sheet), if present.

    This is what turns ``GRTYPE == 2`` into "Adjusted cohort" and ``CONTROL == 1``
    into "Public". Categorical decoding should always read from here rather than
    from a hand-typed mapping, so a taxonomy revision surfaces as a join failure
    instead of a silently wrong label.
    """
    workbook = _open(source)
    for candidate in ("frequencies", "valuesets", "codevalues"):
        sheet = _sheet(workbook, candidate)
        if sheet is not None:
            return _sheet_frame(sheet)
    return pd.DataFrame()


def read_intro(source) -> str:
    """Return the dictionary Introduction sheet as plain text.

    This is the authoritative statement of what period a file describes, and it is
    the single most important cell to read before building a panel: the filename
    year is not the reference period. ``EFFY2023`` covers July 1 2022 to June 30
    2023; ``SFA2223`` is the 2022-23 aid year; ``OM2023`` reports 8-year outcomes
    for a cohort that entered in 2015-16.
    """
    workbook = _open(source)
    sheet = _sheet(workbook, "introduction")
    if sheet is None:
        return ""
    lines: list[str] = []
    for row in sheet.iter_rows(values_only=True):
        text = " ".join(str(c).strip() for c in row if c is not None).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def assert_reference_period(source, *, expect: str, table: str = "") -> str:
    """Fail loudly if a dictionary's Introduction does not mention an expected period.

    Parameters
    ----------
    expect
        A regular expression describing the period the notebook assumes, e.g.
        ``r"July 1, 2022"`` or ``r"2022-23|2022-2023"``.

    Raises
    ------
    AssertionError
        If the Introduction text does not match. This is deliberately a hard failure:
        a silently mismatched reference period corrupts every downstream year
        comparison, and it is invisible in the data itself.
    """
    intro = read_intro(source)
    if not intro:
        raise AssertionError(f"{table or source}: no Introduction sheet to verify against")
    normalised = re.sub(r"[\u2010-\u2015\u2212]", "-", intro)
    normalised = normalised.replace("\u2019", "'").replace("\u00a0", " ")
    if not re.search(expect, normalised, flags=re.IGNORECASE):
        raise AssertionError(
            f"{table or source}: reference period {expect!r} not found in Introduction. "
            f"First 400 characters were:\n{normalised[:400]}"
        )
    return intro


def imputation_partner(varname: str) -> str:
    """Return the conventional imputation-flag column name for a variable.

    IPEDS pairs most reported numerics with an ``X``-prefixed flag recording whether
    the value was reported, imputed, or generated. Chapter 3 requires these to be
    loaded alongside the values they qualify, because an imputed value and a reported
    value are not the same evidence.
    """
    return f"X{varname.upper()}"
