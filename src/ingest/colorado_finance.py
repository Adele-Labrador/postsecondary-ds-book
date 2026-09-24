"""Campus-level finances for Colorado public institutions from IPEDS Finance.

Reads the NCES IPEDS Finance component for public (GASB) institutions,
``F{AA}{AA+1}_F1A``, for fiscal years 2014-15 through 2023-24, and pairs it with
12-month FTE from ``EFIA{AA+1}`` (academic year 20AA-AA+1, the same year as the
finance file). Writes ``dashboard/data/colorado_finance.json`` for the Colorado
panel.

Colorado reporting quirk
------------------------
Colorado does not appropriate General Fund to institutions directly. State
support reaches them two ways (C.R.S. 23-18):

* **College Opportunity Fund (COF) stipends**, paid per resident credit hour on
  the student's behalf. Institutions book these as *tuition*, so IPEDS
  ``F1B01`` (net tuition and fees) includes them.
* **Fee-for-service contracts**, which institutions book as *state operating
  grants and contracts* (``F1B03``), alongside other state grants and
  contracts such as research and state student aid.

As a result IPEDS ``F1B11`` (state appropriations) is near zero for most
Colorado campuses, and IPEDS cannot isolate formula funding. This module keeps
the reported lines separate and labels them for what they contain. Formula
funding by governing board comes from the JBC in :mod:`src.ingest.colorado`.

PERA pension accounting (GASB 68/75) puts large non-cash swings into fringe
benefits for most campuses (CU is largely outside PERA), so function totals
jump between years. Salaries and wages by function are included as a steadier
series.

Two IPEDS units combine campuses the state reports separately: UNITID 126562
is CU Denver and CU Anschutz Medical Campus, and 126818 is CSU Fort Collins
including Professional Veterinary Medicine and the CSU agencies.

Usage (from the repository root)::

    python -m src.ingest.colorado_finance
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.ingest.build_dashboard_data_nces import RAW_DIR as NCES_RAW
from src.ingest.build_dashboard_data_nces import fetch_component
from src.ingest.colorado import BOARDS, CPI_URL, INSTITUTIONS, RAW_DIR, _download

OUT = Path("dashboard/data/colorado_finance.json")
FIRST_YEAR, LAST_YEAR = 2014, 2023  # fiscal years 2014-15 .. 2023-24 (start year)
CPI_BASE = "FY 2023-24"
# Semiannual Denver-Aurora-Lakewood CPI-U. The monthly/bimonthly series
# (CUURS48BSA0) has a gap from 1987 to late 2017, when Denver was published
# twice a year only; the semiannual series is continuous.
CPI_SERIES = "CUUSS48BSA0"

# Display names for IPEDS reporting units that combine state campuses.
UNIT_NAMES = {
    126562: "CU Denver | Anschutz",
    126818: "Colorado State University (Fort Collins, incl. vet med)",
}

# IPEDS F1A variables (NCES F1A data dictionary). Each measure sums its codes.
REVENUE = {
    "tuition": ("F1B01",),  # net tuition and fees; includes COF stipends in Colorado
    "state": (
        "F1B03",
        "F1B11",
        "F1B14",
    ),  # state op. grants/contracts, appropriations, nonop. grants
    "local": ("F1B12",),  # local appropriations and district taxes
    "federal": ("F1B13",),  # federal nonoperating grants (mostly Pell)
}
EXPENSE = {
    "instruction": ("F1C011",),
    "research": ("F1C021",),
    "publicService": ("F1C031",),
    "academicSupport": ("F1C051",),
    "studentServices": ("F1C061",),
    "institutionalSupport": ("F1C071",),
    "scholarships": ("F1C101",),  # net of discounts and allowances
}
# Salaries and wages by function. Colorado's PERA campuses carry large non-cash
# pension and OPEB accruals (GASB 68/75) in fringe benefits, which are spread
# across function totals and swing by tens of millions a year, sometimes below
# zero. Salaries and wages exclude them, so they are the steadier trend measure.
SALARIES = {
    "instructionSalaries": ("F1C012",),
    "academicSupportSalaries": ("F1C052",),
    "studentServicesSalaries": ("F1C062",),
    "benefits": ("F1C193",),  # total employee fringe benefits, all functions
}
TOTALS = {
    "totalRevenue": ("F1B27",),  # operating + nonoperating revenues
    "totalExpense": ("F1C191",),
    "discounts": ("F1E08",),  # discounts and allowances applied to tuition and fees
}
FTE_CODES = ("FTEUG", "FTEGD")  # NCES per-FTE convention (EFIA dictionary)


def fiscal_label(start: int) -> str:
    return f"FY {start}-{str(start + 1)[2:]}"


def finance_stem(start: int) -> str:
    """``F1415_F1A`` for fiscal year 2014-15."""
    a = start % 100
    return f"F{a:02d}{(a + 1) % 100:02d}_F1A"


def semiannual_fiscal_cpi(lines: list[str], series: str = CPI_SERIES) -> dict[str, float]:
    """July-June fiscal-year CPI: mean of S02 (Jul-Dec) of Y and S01 (Jan-Jun) of Y+1."""
    halves: dict[tuple[int, str], float] = {}
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 4 and parts[0] == series and parts[2] in ("S01", "S02"):
            halves[(int(parts[1]), parts[2])] = float(parts[3])
    out = {}
    for (year, period), value in halves.items():
        if period == "S02" and (year + 1, "S01") in halves:
            out[fiscal_label(year)] = round((value + halves[(year + 1, "S01")]) / 2, 3)
    return out


def load_cpi(cdhe_dir: Path = RAW_DIR) -> dict[str, float]:
    path = _download(CPI_URL, cdhe_dir / "cu.data.1.AllItems.txt")
    return semiannual_fiscal_cpi(path.read_text().splitlines())


def units() -> list[dict]:
    """One record per IPEDS UNITID, in state list order, with its board."""
    seen: dict[int, dict] = {}
    for name, board, unitid, _ in INSTITUTIONS:
        rec = seen.setdefault(
            unitid,
            {
                "unitid": unitid,
                "name": UNIT_NAMES.get(unitid, name),
                "board": board,
                "campuses": [],
            },
        )
        rec["campuses"].append(name)
    return list(seen.values())


def measure(frame: pd.DataFrame, unitid: int, codes: tuple[str, ...]) -> int | None:
    """Sum the given variables for one unit; None if every value is missing."""
    if unitid not in frame.index:
        return None
    vals = pd.to_numeric(frame.loc[unitid, list(codes)], errors="coerce")
    return None if vals.isna().all() else int(round(vals.fillna(0).sum()))


def discount_rate(net_tuition: int | None, discounts: int | None) -> float | None:
    """Discounts as a share of gross tuition (net + discounts)."""
    if net_tuition is None or discounts is None or net_tuition + discounts <= 0:
        return None
    return round(discounts / (net_tuition + discounts), 4)


def check_totals(frame: pd.DataFrame, unitid: int, tolerance: int = 2) -> None:
    """Total revenue must equal operating plus nonoperating revenue."""
    op, nonop, total = (measure(frame, unitid, (c,)) for c in ("F1B09", "F1B19", "F1B27"))
    if None not in (op, nonop, total) and abs(op + nonop - total) > tolerance:
        raise ValueError(f"{unitid}: F1B09 + F1B19 = {op + nonop:,} but F1B27 = {total:,}")


def build(nces_dir: Path = NCES_RAW, cdhe_dir: Path = RAW_DIR, out: Path = OUT) -> dict:
    years = list(range(FIRST_YEAR, LAST_YEAR + 1))
    labels = [fiscal_label(y) for y in years]
    fin, fte, provisional = {}, {}, []
    for y in years:
        fin[y] = fetch_component(finance_stem(y), nces_dir)
        fte[y] = fetch_component(f"EFIA{y + 1}", nces_dir)
        if not fin[y].attrs["source_file"].lower().endswith("_rv.csv"):
            provisional.append(fiscal_label(y))

    cpi = load_cpi(cdhe_dir)
    deflator = [round(cpi[CPI_BASE] / cpi[lab], 5) for lab in labels]

    records = []
    for u in units():
        uid = u["unitid"]
        for y in years:
            check_totals(fin[y], uid)
        series = {
            key: [measure(fin[y], uid, codes) for y in years]
            for key, codes in {**REVENUE, **EXPENSE, **SALARIES, **TOTALS}.items()
        }
        series["fte"] = [measure(fte[y], uid, FTE_CODES) for y in years]
        series["fteUg"] = [measure(fte[y], uid, ("FTEUG",)) for y in years]
        series["discountRate"] = [
            discount_rate(t, d) for t, d in zip(series["tuition"], series["discounts"])
        ]
        records.append({**u, **series})

    data = {
        "meta": {
            "years": labels,
            "provisional": provisional,
            "deflator": deflator,
            "deflatorBase": CPI_BASE,
            "cpiSeries": CPI_SERIES,
            "boards": {bid: name for bid, name, _ in BOARDS},
            "variables": {
                k: list(v) for k, v in {**REVENUE, **EXPENSE, **SALARIES, **TOTALS}.items()
            }
            | {"fte": list(FTE_CODES)},
            "sources": {
                "finance": "https://nces.ed.gov/ipeds/use-the-data",
                "dictionary": "https://nces.ed.gov/ipeds/survey-components/2",
                "cpi": "https://www.bls.gov/regions/mountain-plains/co_denver_msa.htm",
            },
        },
        "units": records,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))
    return data


def main() -> None:
    data = build()
    last = data["meta"]["years"][-1]
    print(f"Wrote {OUT}: {len(data['units'])} IPEDS units, {data['meta']['years'][0]}..{last}")
    if data["meta"]["provisional"]:
        print("  provisional (no revised release yet):", ", ".join(data["meta"]["provisional"]))


if __name__ == "__main__":
    main()
