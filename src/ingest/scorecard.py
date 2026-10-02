"""College Scorecard earnings and debt for the dashboard.

Reads the "Most Recent Institution-Level Data" file from the U.S. Department
of Education's College Scorecard (https://collegescorecard.ed.gov/data/) and
returns three outcome measures keyed by IPEDS UNITID:

=============  ===================  ==============================================
Field          Scorecard variable   Cohort in the June 10, 2026 release
=============  ===================  ==============================================
earnings4yr    ``MD_EARN_WNE_4YR``  Completers of AY2017-18 and 2018-19, earnings
                                    in CY2022-23, 2024 dollars
earnings10yr   ``MD_EARN_WNE_P10``  Entrants of AY2009-10 and 2010-11 (completers
                                    or not), earnings in CY2020-21, 2022 dollars
gradDebt       ``GRAD_DEBT_MDN``    Completers entering repayment in FY2020-21
=============  ===================  ==============================================

All three cover only students who received federal (Title IV) aid, and the
earnings measures only those working and not enrolled. The cohort years come
from the Scorecard data dictionary's ``Most_Recent_Inst_Cohort_Map`` sheet.

Scorecard reports earnings and debt for the whole 6-digit OPEID family: a main
campus and its branches carry identical values. :func:`attach` records the
family size and marks one campus per family as the anchor, so the dashboard can
count each family once in medians and charts.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

RELEASE = "2026-06-10"
FILE_STEM = "Most-Recent-Cohorts-Institution_06102026"
URL = f"https://ed-public-download.scorecard.network/downloads/{FILE_STEM}.zip"
RAW_DIR = Path("data/raw/scorecard")
USER_AGENT = "postsecondary-ds-book (+https://github.com/Adele-Labrador/postsecondary-ds-book)"

FIELDS = {
    "earnings4yr": "MD_EARN_WNE_4YR",
    "earnings10yr": "MD_EARN_WNE_P10",
    "gradDebt": "GRAD_DEBT_MDN",
}
COHORTS = {
    "earnings4yr": "Completers of 2017-18 and 2018-19; earnings in 2022-23 (2024 dollars)",
    "earnings10yr": "Entrants of 2009-10 and 2010-11; earnings in 2020-21 (2022 dollars)",
    "gradDebt": "Completers entering repayment in FY2020-21",
}


def fetch(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Return Scorecard earnings/debt indexed by UNITID (downloads once, then cached)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    zpath = raw_dir / f"{FILE_STEM}.zip"
    if not zpath.exists():
        request = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=300) as resp:
                zpath.write_bytes(resp.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(
                f"Scorecard file not found at {URL} ({exc.code}). A newer release may "
                "have replaced it: update FILE_STEM from https://collegescorecard.ed.gov/data/"
            ) from exc
    wanted = {"UNITID", "OPEID6", "MAIN", *FIELDS.values()}
    with zipfile.ZipFile(zpath) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX"))
        with zf.open(name) as fh:
            frame = pd.read_csv(fh, usecols=lambda c: c in wanted, dtype=str)
    return tidy(frame)


def tidy(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce raw Scorecard columns: ``PrivacySuppressed``/``NULL`` become missing."""
    out = pd.DataFrame(index=pd.to_numeric(frame["UNITID"]).astype(int).rename("UNITID"))
    out["opeid6"] = frame["OPEID6"].str.strip().str.zfill(6).to_numpy()  # NaN if absent
    out["main"] = (pd.to_numeric(frame["MAIN"], errors="coerce") == 1).to_numpy()
    for key, var in FIELDS.items():
        values = pd.to_numeric(frame[var], errors="coerce").to_numpy()
        out[key] = pd.Series(values, index=out.index).where(lambda s: s > 0)
    return out


def attach(records: list[dict], sc: pd.DataFrame) -> dict:
    """Add Scorecard fields to dashboard records in place; return coverage metadata.

    Adds ``earnings4yr``, ``earnings10yr``, ``gradDebt``, ``opeid6``,
    ``scShared`` (campuses in the dashboard sharing the family's values) and
    ``scAnchor`` (True on the one campus per family counted in aggregates:
    Scorecard's main campus, else the largest by FTE).
    """
    by_id = {r["id"]: r for r in records}
    matched = sc[sc.index.isin(by_id)]
    for uid, row in matched.iterrows():
        rec = by_id[uid]
        rec["opeid6"] = row["opeid6"] if isinstance(row["opeid6"], str) else None
        for key in FIELDS:
            value = row[key]
            rec[key] = int(round(value)) if pd.notna(value) else None

    families: dict[str, list[dict]] = {}
    for rec in records:
        if rec.get("opeid6"):
            families.setdefault(rec["opeid6"], []).append(rec)
    for members in families.values():
        main = [m for m in members if bool(sc.at[m["id"], "main"])]
        pool = main or members
        anchor = max(pool, key=lambda m: (m.get("fte") or 0, -m["id"]))
        for m in members:
            m["scShared"] = len(members)
            m["scAnchor"] = m is anchor
    for rec in records:
        rec.setdefault("opeid6", None)
        rec.setdefault("scShared", None)
        rec.setdefault("scAnchor", None)
        for key in FIELDS:
            rec.setdefault(key, None)

    return {
        "release": RELEASE,
        "file": f"{FILE_STEM}.zip",
        "cohorts": COHORTS,
        "matched": int(len(matched)),
        "families": sum(1 for m in families.values() if len(m) > 1),
    }
