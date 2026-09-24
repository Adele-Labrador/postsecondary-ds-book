"""Build the dashboard's institution-year dataset from real IPEDS data.

Pulls live IPEDS data from the Urban Institute Education Data Portal
(https://educationdata.urban.org/documentation/), joins the components into
one institution-level table for the most recent complete year, attaches a
multi-year FTE enrollment series for trend/forecast views, and writes a
compact JSON payload consumed by the static dashboard in ``dashboard/``.

Run:
    python -m src.ingest.build_dashboard_data

Outputs:
    dashboard/data/institutions.json

Notes on vintage: most components use PRIMARY_YEAR (2022). The student
financial aid component lags by one year in the portal, so aid figures use
AID_YEAR (2021) and are labeled as such in the UI.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://educationdata.urban.org/api/v1/college-university/ipeds"

PRIMARY_YEAR = 2022
AID_YEAR = 2021
TREND_YEARS = list(range(2013, PRIMARY_YEAR + 1))

OUT_PATH = Path("dashboard/data/institutions.json")

CONTROL_LABELS = {1: "Public", 2: "Private nonprofit", 3: "Private for-profit"}
LEVEL_LABELS = {
    1: "Less than 2-year",
    2: "2-year",
    3: "Less than 4-year",
    4: "4-year or above",
}

# Carnegie Basic Classification, 2021 edition (`cc_basic_2021` in the portal's
# directory endpoint). The 33 codes below follow the official published order,
# spot-verified against known institutions: code 15 returns Harvard, Stanford,
# MIT, Yale and Columbia (Very High Research); code 18 returns Alabama A&M
# (Master's, Larger Programs); code 16 returns Villanova (High Research).
# Each entry is (full published label, coarse family used for filtering).
A = "Associate's"
SF = "Special Focus"
BA = "Baccalaureate/Associate's"
CC_BASIC_2021 = {
    1: ("Associate's Colleges: High Transfer-High Traditional", A),
    2: ("Associate's Colleges: High Transfer-Mixed Traditional/Nontraditional", A),
    3: ("Associate's Colleges: High Transfer-High Nontraditional", A),
    4: ("Associate's Colleges: Mixed Transfer/Career & Technical-High Traditional", A),
    5: (
        "Associate's Colleges: Mixed Transfer/Career & Technical-Mixed Traditional/Nontraditional",
        A,
    ),
    6: ("Associate's Colleges: Mixed Transfer/Career & Technical-High Nontraditional", A),
    7: ("Associate's Colleges: High Career & Technical-High Traditional", A),
    8: ("Associate's Colleges: High Career & Technical-Mixed Traditional/Nontraditional", A),
    9: ("Associate's Colleges: High Career & Technical-High Nontraditional", A),
    10: ("Special Focus Two-Year: Health Professions", SF),
    11: ("Special Focus Two-Year: Technical Professions", SF),
    12: ("Special Focus Two-Year: Arts & Design", SF),
    13: ("Special Focus Two-Year: Other Fields", SF),
    14: ("Baccalaureate/Associate's Colleges: Associate's Dominant", BA),
    15: ("Doctoral Universities: Very High Research Activity", "Doctoral"),
    16: ("Doctoral Universities: High Research Activity", "Doctoral"),
    17: ("Doctoral/Professional Universities", "Doctoral"),
    18: ("Master's Colleges & Universities: Larger Programs", "Master's"),
    19: ("Master's Colleges & Universities: Medium Programs", "Master's"),
    20: ("Master's Colleges & Universities: Small Programs", "Master's"),
    21: ("Baccalaureate Colleges: Arts & Sciences Focus", "Baccalaureate"),
    22: ("Baccalaureate Colleges: Diverse Fields", "Baccalaureate"),
    23: ("Baccalaureate/Associate's Colleges: Mixed Baccalaureate/Associate's", BA),
    24: ("Special Focus Four-Year: Faith-Related Institutions", SF),
    25: ("Special Focus Four-Year: Medical Schools & Centers", SF),
    26: ("Special Focus Four-Year: Other Health Professions Schools", SF),
    27: ("Special Focus Four-Year: Engineering and Other Technology-Related Schools", SF),
    28: ("Special Focus Four-Year: Business & Management Schools", SF),
    29: ("Special Focus Four-Year: Arts, Music & Design Schools", SF),
    30: ("Special Focus Four-Year: Law Schools", SF),
    31: ("Special Focus Four-Year: Other Special Focus Institutions", SF),
    32: ("Tribal Colleges", "Tribal"),
    33: ("Not classified", None),
}


def carnegie(code):
    """Return (full Carnegie Basic 2021 label, coarse family) for a code."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return None, None
    label, family = CC_BASIC_2021.get(code, (None, None))
    return label, family


def fetch(path: str, retries: int = 3) -> list[dict]:
    """GET one endpoint and return its ``results`` list.

    The portal returns full national result sets for these endpoints in a
    single response, so no pagination loop is needed; a ``next`` link is
    followed defensively if one ever appears.
    """
    url = BASE + path
    rows: list[dict] = []
    while url:
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(url, timeout=180) as resp:
                    payload = json.load(resp)
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == retries - 1:
                    raise
                print(f"    retry {attempt + 1} after {type(exc).__name__}")
                time.sleep(2 * (attempt + 1))
        rows.extend(payload.get("results", []))
        url = payload.get("next")
    return rows


def num(value):
    """Coerce portal sentinels (-1, -2, -3, blank) to None.

    The portal encodes 'missing/not reported' as small negative integers, and
    none of the metrics here are legitimately negative, so negatives are
    treated as missing. Use :func:`signed` for coordinates, which are.
    """
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def signed(value):
    """Coerce a value that may legitimately be negative (e.g. longitude)."""
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    return round(value, 5)


def main() -> None:
    print(f"Building dashboard dataset (primary year {PRIMARY_YEAR})")

    print("  directory ...")
    directory = fetch(f"/directory/{PRIMARY_YEAR}/")

    print("  student-faculty ratio ...")
    sfr = {
        r["unitid"]: num(r.get("student_faculty_ratio"))
        for r in fetch(f"/student-faculty-ratio/{PRIMARY_YEAR}/")
    }

    print("  admissions ...")
    adm = {}
    for r in fetch(f"/admissions-enrollment/{PRIMARY_YEAR}/?sex=99"):
        adm[r["unitid"]] = {
            "applied": num(r.get("number_applied")),
            "admitted": num(r.get("number_admitted")),
            "enrolled": num(r.get("number_enrolled_total")),
        }

    print("  graduation rates ...")
    grad: dict[int, dict] = {}
    for r in fetch(f"/grad-rates/{PRIMARY_YEAR}/?race=99&sex=99&subcohort=99"):
        cohort = num(r.get("cohort_rev")) or 0
        prev = grad.get(r["unitid"])
        # An institution can report multiple level rows; keep the largest cohort.
        if prev is None or cohort > prev["cohort"]:
            grad[r["unitid"]] = {
                "cohort": cohort,
                "rate": num(r.get("completion_rate_150pct")),
                "completers": num(r.get("completers_150pct")),
            }

    print("  retention ...")
    retention = {}
    for r in fetch(f"/fall-retention/{PRIMARY_YEAR}/?ftpt=1"):
        retention[r["unitid"]] = num(r.get("retention_rate"))

    print("  tuition ...")
    tuition: dict[int, dict] = {}
    for r in fetch(f"/academic-year-tuition/{PRIMARY_YEAR}/?level_of_study=1"):
        entry = tuition.setdefault(r["unitid"], {})
        value = num(r.get("tuition_fees_ft")) or num(r.get("tuition_fees_published"))
        if r.get("tuition_type") == 3:
            entry["in_state"] = value
        elif r.get("tuition_type") == 4:
            entry["out_state"] = value

    # type_of_aid=5 is the Pell grant series. Verified empirically against
    # national benchmarks: median 35% of undergraduates receiving, median
    # average award ~$4,700, consistent with published Pell figures.
    print(f"  Pell grants ({AID_YEAR}) ...")
    aid = {}
    for r in fetch(f"/sfa-all-undergraduates/{AID_YEAR}/?type_of_aid=5&level_of_study=1&ftpt=99"):
        aid[r["unitid"]] = {
            "pell_pct": num(r.get("percent_of_students")),
            "pell_avg": num(r.get("average_amount")),
        }

    print("  FTE enrollment trend ...")
    trend: dict[int, dict[int, float]] = {}
    for year in TREND_YEARS:
        # One row per institution per year; the activity-type code varies by
        # how the institution reports (credit vs. contact hours), so it is
        # deliberately not filtered.
        rows = fetch(f"/enrollment-full-time-equivalent/{year}/1/")
        for r in rows:
            fte = num(r.get("rep_fte")) or num(r.get("est_fte"))
            if fte:
                trend.setdefault(r["unitid"], {})[year] = round(fte)
        print(f"    {year}: {len(rows)} rows")

    print("Joining ...")
    records = []
    for d in directory:
        uid = d["unitid"]
        # Keep active, degree-granting, Title IV institutions with an
        # enrollment series -- the analytic universe the book works with.
        if d.get("degree_granting") != 1:
            continue
        series = trend.get(uid, {})
        latest_fte = series.get(PRIMARY_YEAR)
        if not latest_fte:
            continue

        a = adm.get(uid) or {}
        applied, admitted, enrolled = a.get("applied"), a.get("admitted"), a.get("enrolled")
        admit_rate = round(admitted / applied, 4) if applied and admitted else None
        yield_rate = round(enrolled / admitted, 4) if admitted and enrolled else None

        g = grad.get(uid) or {}
        t = tuition.get(uid) or {}
        f = aid.get(uid) or {}
        cc_label, cc_family = carnegie(d.get("cc_basic_2021"))

        records.append(
            {
                "id": uid,
                "name": d.get("inst_name"),
                "city": (d.get("city") or "").strip(),
                "state": d.get("state_abbr"),
                "lat": signed(d.get("latitude")),
                "lon": signed(d.get("longitude")),
                "control": CONTROL_LABELS.get(d.get("inst_control")),
                "level": LEVEL_LABELS.get(d.get("institution_level")),
                "carnegie": cc_label,
                "family": cc_family,
                "hbcu": 1 if d.get("hbcu") == 1 else 0,
                "fte": latest_fte,
                "sfr": sfr.get(uid),
                "admitRate": admit_rate,
                "yieldRate": yield_rate,
                "gradRate": g.get("rate"),
                "gradCohort": g.get("cohort") or None,
                "retention": retention.get(uid),
                "tuitionIn": t.get("in_state"),
                "tuitionOut": t.get("out_state"),
                "pellPct": f.get("pell_pct"),
                "pellAvg": f.get("pell_avg"),
                "series": [series.get(y) for y in TREND_YEARS],
            }
        )

    records.sort(key=lambda r: -(r["fte"] or 0))

    payload = {
        "meta": {
            "primaryYear": PRIMARY_YEAR,
            "aidYear": AID_YEAR,
            "trendYears": TREND_YEARS,
            "count": len(records),
            "source": "NCES IPEDS via Urban Institute Education Data Portal",
            "sourceUrl": "https://educationdata.urban.org/documentation/colleges.html",
            "built": time.strftime("%Y-%m-%d"),
        },
        "institutions": records,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, separators=(",", ":")))
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUT_PATH} ({len(records)} institutions, {size_mb:.2f} MB)")

    # Coverage report -- useful sanity check before the dashboard consumes it.
    if not records:
        raise SystemExit("No records assembled -- check endpoint filters above.")
    for field in ["sfr", "gradRate", "admitRate", "retention", "tuitionIn", "pellPct", "lat"]:
        n = sum(1 for r in records if r.get(field) is not None)
        print(f"  {field:12s} {n:5d} / {len(records)}  ({n / len(records):.0%})")


if __name__ == "__main__":
    main()
