"""Build the dashboard dataset directly from NCES IPEDS Complete Data Files.

This is the primary-source counterpart to ``build_dashboard_data.py``, which
reads the same IPEDS collections through the Urban Institute Education Data
Portal. Both write ``dashboard/data/institutions.json`` in the same schema.

Field definitions were reconciled against the Urban-built 2022 file, one field
at a time, before this builder was trusted for a new year. Every field
reproduced 100% of the shipped values once file versions were matched:

======================  ======================================  =============
Dashboard field         NCES source (``Y`` = dashboard year)    Match (2022)
======================  ======================================  =============
fte, series             ``EFIA{Y+1}.FTEUG``                     3,716 / 3,716
sfr                     ``EF{Y}D.STUFACR``                      3,707 / 3,707
retention               ``EF{Y}D.RET_PCF / 100``                3,305 / 3,305
admitRate, yieldRate    ``ADM{Y}``  ADMSSN/APPLCN, ENRLT/ADMSSN 1,826 / 1,826
tuitionIn / tuitionOut  ``IC{Y}_AY``  TUITION2+FEE2 / 3+FEE3     3,395 / 3,395
tuitionDistrict         ``IC{Y}_AY``  TUITION1+FEE1              (not in portal build)
pellPct, pellAvg        ``SFA{A}{A+1}``  UPGRNTP / 100, UPGRNTA  3,690 / 3,690
gradRate, gradCohort    ``GR{Y+1}``  see :func:`grad_rates`      2,224 / 2,224
======================  ======================================  =============

Three alignment facts matter and are easy to get wrong:

* **Year labels.** Urban labels 12-month enrollment and graduation rates by the
  start of the academic year; NCES labels files by collection year. Dashboard
  year ``Y`` FTE is therefore ``EFIA{Y+1}`` and its graduation rates ``GR{Y+1}``.
* **Revised files.** NCES republishes corrected components with an ``_rv``
  suffix. This builder always prefers ``_rv``; the Urban file used the original
  release for some components, which accounts for small (<3%) differences.
* **Rounding.** Graduation rates round half *up* to two decimals (0.625 ->
  0.63), matching the published values. Python's ``round`` rounds half to
  even, so the rate is computed with exact integer arithmetic instead.

Usage (from the repository root)::

    python -m src.ingest.build_dashboard_data_nces --year 2023

Raw ZIPs are cached in ``data/raw/nces`` (git-ignored).
"""

from __future__ import annotations

import argparse
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from src.ingest.build_dashboard_data import CC_BASIC_2021, CONTROL_LABELS

NCES_BASE = "https://nces.ed.gov/ipeds/datacenter/data"
RAW_DIR = Path("data/raw/nces")
OUT_PATH = Path("dashboard/data/institutions.json")
FIRST_TREND_YEAR = 2013
USER_AGENT = "postsecondary-ds-book/1.0 (+https://github.com/Adele-Labrador/postsecondary-ds-book)"

# NCES ICLEVEL codes differ from the portal's institution_level codes.
NCES_LEVEL_LABELS = {1: "4-year or above", 2: "2-year", 3: "Less than 2-year"}

# GR file GRTYPE codes (from the NCES GR data dictionary).
# (revised cohort, adjusted cohort, completers within 150% of normal time)
GR_4YR = (1, 2, 3)
GR_2YR = (27, 29, 30)


class MissingFile(RuntimeError):
    """Raised when NCES has not published a requested component file."""


def fetch_component(stem: str, raw_dir: Path = RAW_DIR, retries: int = 4) -> pd.DataFrame:
    """Return one component file as a DataFrame indexed by UNITID.

    Downloads ``<stem>.zip`` on first use. Prefers the revised (``_rv``) CSV
    when the archive contains one.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    zpath = raw_dir / f"{stem}.zip"
    if not zpath.exists():
        url = f"{NCES_BASE}/{stem}.zip"
        # A 404 means "not published"; anything else is a transient failure and
        # is retried, so a flaky connection is never mistaken for a missing file.
        for attempt in range(1, retries + 1):
            try:
                # Identify the client; NCES may rate-limit repeated bulk downloads.
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=300) as resp:
                    zpath.write_bytes(resp.read())
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise MissingFile(f"{stem} is not published by NCES yet") from exc
                if attempt == retries:
                    raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == retries:
                    raise
            time.sleep(3 * attempt)
    with zipfile.ZipFile(zpath) as zf:
        csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        revised = [n for n in csvs if n.lower().endswith("_rv.csv")]
        name = (revised or csvs)[0]
        frame = pd.read_csv(io.BytesIO(zf.read(name)), encoding="latin-1", low_memory=False)
    frame.columns = (
        frame.columns.str.replace("\ufeff", "").str.replace("ï»¿", "").str.upper().str.strip()
    )
    frame = frame.set_index("UNITID")
    frame.attrs["source_file"] = name
    return frame


def num(series: pd.Series) -> pd.Series:
    """Numeric coercion; blanks and negative sentinels become NaN."""
    out = pd.to_numeric(series, errors="coerce")
    return out.where(out >= 0)


def round_half_up(numerator: int, denominator: int, places: int = 2) -> float:
    """Exact half-up rounding of ``numerator / denominator``."""
    scale = 10**places
    return ((2 * scale * numerator + denominator) // (2 * denominator)) / scale


def grad_rates(gr: pd.DataFrame) -> dict[int, dict]:
    """Graduation rate within 150% of normal time, per institution.

    Uses the 4-year cohort rows for 4-year institutions and the
    degree/certificate-seeking cohort rows for 2-year institutions. When an
    institution reports both, the larger revised cohort wins, matching the
    portal builder. Rate = completers / adjusted cohort.
    """
    totals = gr.reset_index().pivot_table(
        index="UNITID", columns="GRTYPE", values="GRTOTLT", aggfunc="sum"
    )
    out: dict[int, dict] = {}
    for uid, row in totals.iterrows():
        best = None
        for rev_code, adj_code, comp_code in (GR_4YR, GR_2YR):
            rev, adj, comp = (row.get(c) for c in (rev_code, adj_code, comp_code))
            if pd.isna(adj) or pd.isna(comp) or adj <= 0:
                continue
            candidate = {
                "cohort": int(rev) if pd.notna(rev) else int(adj),
                "rate": round_half_up(int(comp), int(adj)),
            }
            if best is None or candidate["cohort"] > best["cohort"]:
                best = candidate
        if best:
            out[int(uid)] = best
    return out


def clean(value, places: int | None = None):
    if value is None or pd.isna(value):
        return None
    value = float(value)
    return round(value, places) if places is not None else value


def build(year: int, aid_year: int | None = None, grad_file_year: int | None = None) -> dict:
    aid_year = aid_year if aid_year is not None else year - 1
    sources: dict[str, str] = {}

    def load(stem: str) -> pd.DataFrame:
        frame = fetch_component(stem)
        sources[stem] = frame.attrs["source_file"]
        print(f"  {stem:10} <- {frame.attrs['source_file']} ({len(frame):,} rows)")
        return frame

    print(f"Building dashboard dataset from NCES files (year {year}, aid {aid_year})")
    hd = load(f"HD{year}")
    efd = load(f"EF{year}D")
    adm = load(f"ADM{year}")
    ic = load(f"IC{year}_AY")
    sfa = load(f"SFA{aid_year % 100:02d}{(aid_year + 1) % 100:02d}")

    # Graduation rates publish a year after the other components. Fall back to
    # the most recent final file rather than silently mixing provisional data.
    if grad_file_year is None:
        try:
            gr = load(f"GR{year + 1}")
            grad_file_year = year + 1
        except MissingFile:
            print(f"  GR{year + 1} not published; using GR{year}")
            gr = load(f"GR{year}")
            grad_file_year = year
    else:
        gr = load(f"GR{grad_file_year}")
    grad = grad_rates(gr)

    trend_years = list(range(FIRST_TREND_YEAR, year + 1))
    fte = {y: num(load(f"EFIA{y + 1}")["FTEUG"]) for y in trend_years}

    sfr = num(efd["STUFACR"])
    retention = num(efd["RET_PCF"]) / 100
    applied, admitted, enrolled = (num(adm[c]) for c in ("APPLCN", "ADMSSN", "ENRLT"))
    # In-district is what local residents pay; below in-state at ~29% of public
    # 2-year colleges (e.g. community college districts in TX, CA, IL).
    tuition_district = num(ic["TUITION1"]) + num(ic["FEE1"])
    tuition_in = num(ic["TUITION2"]) + num(ic["FEE2"])
    tuition_out = num(ic["TUITION3"]) + num(ic["FEE3"])
    pell_pct = num(sfa["UPGRNTP"]) / 100
    pell_avg = num(sfa["UPGRNTA"])

    def at(series: pd.Series, uid):
        return series.get(uid) if uid in series.index else None

    records = []
    for uid, d in hd.iterrows():
        if d.get("DEGGRANT") != 1:
            continue
        latest = at(fte[year], uid)
        if latest is None or pd.isna(latest) or latest <= 0:
            continue

        ap, ad, en = at(applied, uid), at(admitted, uid), at(enrolled, uid)
        admit_rate = round(ad / ap, 4) if ap and ad and pd.notna(ap) and pd.notna(ad) else None
        yield_rate = round(en / ad, 4) if ad and en and pd.notna(ad) and pd.notna(en) else None

        cc_label, cc_family = CC_BASIC_2021.get(int(d.get("C21BASIC", -1)), (None, None))
        lat, lon = pd.to_numeric(d.get("LATITUDE"), errors="coerce"), pd.to_numeric(
            d.get("LONGITUD"), errors="coerce"
        )
        g = grad.get(int(uid), {})

        records.append(
            {
                "id": int(uid),
                "name": str(d.get("INSTNM")).strip(),
                "city": str(d.get("CITY") or "").strip(),
                "state": d.get("STABBR"),
                "lat": round(float(lat), 5) if pd.notna(lat) and lat != 0 else None,
                "lon": round(float(lon), 5) if pd.notna(lon) and lon != 0 else None,
                "control": CONTROL_LABELS.get(int(d.get("CONTROL", -1))),
                "level": NCES_LEVEL_LABELS.get(int(d.get("ICLEVEL", -1))),
                "carnegie": cc_label,
                "family": cc_family,
                "hbcu": 1 if d.get("HBCU") == 1 else 0,
                "fte": int(round(latest)),
                "sfr": clean(at(sfr, uid)),
                "admitRate": admit_rate,
                "yieldRate": yield_rate,
                "gradRate": g.get("rate"),
                "gradCohort": g.get("cohort") or None,
                "retention": clean(at(retention, uid), 4),
                "tuitionDistrict": clean(at(tuition_district, uid)),
                "tuitionIn": clean(at(tuition_in, uid)),
                "tuitionOut": clean(at(tuition_out, uid)),
                "pellPct": clean(at(pell_pct, uid), 4),
                "pellAvg": clean(at(pell_avg, uid)),
                "series": [
                    (
                        int(round(v))
                        if (v := at(fte[y], uid)) is not None and pd.notna(v) and v > 0
                        else None
                    )
                    for y in trend_years
                ],
            }
        )

    records.sort(key=lambda r: -r["fte"])
    return {
        "meta": {
            "primaryYear": year,
            "aidYear": aid_year,
            # Label graduation rates in the same start-of-year convention as
            # everything else, so GR2023 (reported 2023-24) reads as 2022.
            "gradYear": grad_file_year - 1,
            "trendYears": trend_years,
            "count": len(records),
            "source": "NCES IPEDS Complete Data Files",
            "sourceUrl": "https://nces.ed.gov/ipeds/use-the-data",
            "files": sources,
            "built": time.strftime("%Y-%m-%d"),
        },
        "institutions": records,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--aid-year", type=int)
    parser.add_argument("--grad-file-year", type=int)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)

    payload = build(args.year, args.aid_year, args.grad_file_year)
    if not payload["institutions"]:
        raise SystemExit("No records assembled -- check component files.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")))
    recs = payload["institutions"]
    print(f"Wrote {args.out} ({len(recs):,} institutions, {args.out.stat().st_size / 1e6:.2f} MB)")
    for key in ("sfr", "gradRate", "admitRate", "retention", "tuitionIn", "pellPct", "lat"):
        print(f"  {key:10} {sum(r[key] is not None for r in recs):,}")


if __name__ == "__main__":
    main()
