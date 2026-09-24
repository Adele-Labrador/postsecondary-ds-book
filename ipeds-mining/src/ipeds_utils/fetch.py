"""Retrieval and unpacking of IPEDS Data Center distribution files.

Every IPEDS survey file is published as a zipped CSV at a predictable URL, with a
parallel zipped Excel dictionary. This module is the only place in the project that
touches the network, so provenance capture happens in exactly one location.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA_URL = "https://nces.ed.gov/ipeds/datacenter/data/{table}.zip"
DICT_URL = "https://nces.ed.gov/ipeds/datacenter/data/{table}_Dict.zip"

DEFAULT_TIMEOUT = 120
USER_AGENT = "ipeds-mining/1.0 (educational research; contact: instructor@example.edu)"


class FetchError(RuntimeError):
    """Raised when a table cannot be retrieved from the IPEDS Data Center."""


def _get(url: str, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    if response.status_code != 200:
        raise FetchError(f"HTTP {response.status_code} for {url}")
    if not response.content[:2] == b"PK":
        raise FetchError(
            f"{url} did not return a zip archive (got {response.content[:40]!r}). "
            "The Data Center returns an HTML error page for unrecognised table names, "
            "so check the table spelling against the IPEDS complete-data-files list."
        )
    return response.content


def fetch(table: str, raw_dir: str | Path = "data/raw", *, refresh: bool = False) -> dict:
    """Download one IPEDS table plus its dictionary and record provenance.

    Parameters
    ----------
    table
        Native IPEDS table name, exactly as it appears in the Data Center, e.g.
        ``"HD2023"``, ``"F2223_F1A"``, ``"GR200_23"``. Case matters in the URL.
    raw_dir
        Destination directory for the two zip archives.
    refresh
        Re-download even if the archives are already present. Default is to reuse
        the cached copy so a notebook can be re-run offline.

    Returns
    -------
    dict
        Provenance record with local paths, SHA-256 digests, byte counts, and the
        UTC retrieval timestamp. Write this into ``docs/provenance/``.

    Notes
    -----
    A few tables have no published dictionary. That is recorded as
    ``dict_path: None`` rather than raised, because the CSV is still usable; the
    caller simply cannot schema-lock against official labels.
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "table": table,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_url": DATA_URL.format(table=table),
        "dict_url": DICT_URL.format(table=table),
    }

    data_path = raw_dir / f"{table}.zip"
    if refresh or not data_path.exists():
        payload = _get(record["data_url"])
        data_path.write_bytes(payload)
    record["data_path"] = str(data_path)
    record["data_sha256"] = _sha256(data_path)
    record["data_bytes"] = data_path.stat().st_size

    dict_path = raw_dir / f"{table}_Dict.zip"
    if refresh or not dict_path.exists():
        try:
            dict_path.write_bytes(_get(record["dict_url"]))
        except FetchError:
            dict_path = None
    if dict_path is not None and dict_path.exists():
        record["dict_path"] = str(dict_path)
        record["dict_sha256"] = _sha256(dict_path)
        record["dict_bytes"] = dict_path.stat().st_size
    else:
        record["dict_path"] = None

    return record


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def unzip_csv(zip_path: str | Path) -> tuple[bytes, str]:
    """Return the bytes of the single CSV inside an IPEDS data archive.

    IPEDS data archives contain one CSV, but the name is not always the table name
    and revised releases add a second ``_rv`` member. When both are present the
    revised file is preferred, because it carries the corrected values that NCES
    published after the provisional release.
    """
    with zipfile.ZipFile(zip_path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise FetchError(f"No CSV member inside {zip_path}")
        revised = [n for n in members if "_rv" in n.lower()]
        chosen = sorted(revised or members, key=len)[0]
        return archive.read(chosen), chosen


def unzip_dict(zip_path: str | Path) -> tuple[io.BytesIO, str]:
    """Return an in-memory handle to the Excel dictionary inside an archive."""
    with zipfile.ZipFile(zip_path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith((".xlsx", ".xls"))]
        if not members:
            raise FetchError(f"No Excel dictionary inside {zip_path}")
        chosen = sorted(members, key=len)[0]
        return io.BytesIO(archive.read(chosen)), chosen


def write_provenance(records: list[dict], path: str | Path) -> Path:
    """Persist provenance records as JSON alongside the curated outputs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, sort_keys=True))
    return path
