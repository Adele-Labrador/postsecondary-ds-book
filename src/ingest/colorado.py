"""Colorado panel: state resident FTE and state operating funding by governing board.

Builds ``dashboard/data/colorado.json`` from three public sources:

* **Resident FTE** from the Colorado Department of Higher Education (CDHE) FTE
  Student Enrollment Reports (series ``hed1540`` resident, ``hed1539`` resident
  undergraduate, ``hed1538`` all students). These are *state fiscal-year* FTE
  (July-June, 30 credit hours = 1 undergraduate FTE), the enrollment measure the
  funding formula uses. They are not comparable to IPEDS fall 12-month FTE and
  are kept in a separate file for that reason.
* **Formula funding** from Joint Budget Committee (JBC) staff briefings: the
  per-board base for "student stipends, fee-for-service contracts, specialty
  education, and grants for local district and area technical colleges". This
  is the pot H.B. 20-1366 allocates. It excludes one-time items (for example the
  FY2024-25 $30M one-time funds) and the FY2025-26 Auraria Higher Education
  Center line, both of which inflate the JBC "General Fund appropriations" table.
* **Denver-Aurora-Lakewood CPI-U** (BLS ``CUURS48BSA0``, bimonthly), averaged
  over each July-June fiscal year to express dollars in FY2025-26 terms.

Every funding value records the briefing URL and page it came from. PDF parsing
needs ``pdfplumber``; the text parsers below are pure functions and are what
the offline tests exercise.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

RAW_DIR = Path("data/raw/cdhe")
OUT = Path("dashboard/data/colorado.json")
USER_AGENT = "postsecondary-ds-book (+https://github.com/Adele-Labrador/postsecondary-ds-book)"

# ── Governing boards ──────────────────────────────────────────────────────────
# (id, display name, regex matching the row label in JBC tables)
BOARDS = [
    (
        "CU",
        "University of Colorado System",
        r"^(University of Colorado System|U\. of Colorado System)",
    ),
    (
        "CSU",
        "Colorado State University System",
        r"^(Colorado State University System|CO State U\. System)",
    ),
    ("CCCS", "Colorado Community College System", r"^Community College System"),
    ("MSU", "Metropolitan State University of Denver", r"^Metropolitan State"),
    (
        "UNC",
        "University of Northern Colorado",
        r"^(University of Northern Colorado|U\. of Northern Colorado)",
    ),
    ("CMU", "Colorado Mesa University", r"^Colorado Mesa"),
    ("CSM", "Colorado School of Mines", r"^Colorado School of Mines"),
    ("FLC", "Fort Lewis College", r"^Fort Lewis"),
    ("WCU", "Western Colorado University", r"^Western"),
    ("ASU", "Adams State University", r"^Adams State"),
    ("AIMS", "Aims Community College", r"^Aims"),
    ("CMC", "Colorado Mountain College", r"^Colorado Mountain College"),
    ("ATC", "Area technical colleges", r"^Area Technical"),
]
BOARD_IDS = [b[0] for b in BOARDS]
STATE_BOARDS = BOARD_IDS[:10]  # the ten state governing boards (JBC "sub-total")

# ── Institutions in the CDHE FTE reports ─────────────────────────────────────
# (canonical name, board, IPEDS UNITID, regex matching every historical name)
INSTITUTIONS = [
    ("University of Colorado Boulder", "CU", 126614, r"^University of Colorado-Boulder$"),
    (
        "University of Colorado Colorado Springs",
        "CU",
        126580,
        r"^University of Colorado-Colorado Springs$",
    ),
    (
        "University of Colorado Denver (Downtown)",
        "CU",
        126562,
        r"^University of Colorado Denver - Downtown",
    ),
    (
        "University of Colorado Anschutz Medical Campus",
        "CU",
        126562,
        r"^University of Colorado Denver - Anschutz",
    ),
    (
        "Colorado State University-Fort Collins",
        "CSU",
        126818,
        r"^Colorado State University - Fort Collins$",
    ),
    (
        "CSU Professional Veterinary Medicine",
        "CSU",
        126818,
        r"^Colorado State University - Professional Vet",
    ),
    ("Colorado State University Pueblo", "CSU", 128106, r"^Colorado State University - Pueblo$"),
    ("Fort Lewis College", "FLC", 127185, r"^Fort Lewis College$"),
    ("Colorado School of Mines", "CSM", 126775, r"^Colorado School of Mines$"),
    ("University of Northern Colorado", "UNC", 127741, r"^University of Northern Colorado$"),
    ("Adams State University", "ASU", 126182, r"^Adams State (University|College)$"),
    ("Colorado Mesa University", "CMU", 127556, r"^(Colorado Mesa University|Mesa State College)$"),
    (
        "Metropolitan State University of Denver",
        "MSU",
        127565,
        r"^Metropolitan State (University of Denver|College of Denver)$",
    ),
    (
        "Western Colorado University",
        "WCU",
        128391,
        r"^Western (State )?Colorado University$|^Western State College",
    ),
    ("Arapahoe Community College", "CCCS", 126289, r"^Arapahoe Community College$"),
    ("Colorado Northwestern Community College", "CCCS", 126748, r"^Colorado Northwestern"),
    ("Community College of Aurora", "CCCS", 126863, r"^Community College of Aurora$"),
    ("Community College of Denver", "CCCS", 126942, r"^Community College of Denver$"),
    ("Front Range Community College", "CCCS", 127200, r"^Front Range Community College$"),
    ("Lamar Community College", "CCCS", 127389, r"^Lamar Community College$"),
    ("Morgan Community College", "CCCS", 127617, r"^Morgan Community College$"),
    ("Northeastern Junior College", "CCCS", 127732, r"^Northeastern Junior College$"),
    ("Otero College", "CCCS", 127778, r"^Otero (Junior )?College$"),
    ("Pikes Peak State College", "CCCS", 127820, r"^Pikes Peak (Community|State) College$"),
    ("Pueblo Community College", "CCCS", 127884, r"^Pueblo Community College$"),
    ("Red Rocks Community College", "CCCS", 127909, r"^Red Rocks Community College$"),
    ("Trinidad State College", "CCCS", 128258, r"^Trinidad State (Junior )?College$"),
    ("Aims Community College", "AIMS", 126207, r"^Aims Community College$"),
    ("Colorado Mountain College", "CMC", 126711, r"^Colorado Mountain College$"),
]

# ── FTE reports ──────────────────────────────────────────────────────────────
FTE_SERIES = {"resident": "1540", "residentUg": "1539", "total": "1538"}
FTE_VINTAGES = ("201920", "202425")  # FY2007-08..FY2019-20 and FY2019-20..FY2024-25
FTE_URL = "https://spl.cde.state.co.us/artemis/hedserials/hed{s}internet/hed{s}{v}internet.pdf"

# ── Funding tables in JBC briefings ──────────────────────────────────────────
JBC = "https://content.leg.colorado.gov/sites/default/files/"


@dataclass(frozen=True)
class FundingSource:
    fiscal_year: str  # "FY 2021-22"
    file: str
    url: str
    pages: tuple[int, ...]  # zero-based pdf pages
    marker: str  # parse only text after this marker
    column: int  # which number on the row (0 = first); -1 means col0 + col1
    note: str

    @property
    def cite(self) -> str:
        return f"{self.url}#page={self.pages[0] + 1}"


FUNDING_SOURCES = [
    FundingSource(
        "FY 2019-20",
        "fy2021-22_hedbrf.pdf",
        JBC + "fy2021-22_hedbrf.pdf",
        (35, 36),
        "BASE STATE SUPPORT",
        0,
        "FY2019-20 base in the JBC FY2021-22 briefing, before the FY2020-21 COVID reduction.",
    ),
    FundingSource(
        "FY 2020-21",
        "fy2021-22_hedbrf.pdf",
        JBC + "fy2021-22_hedbrf.pdf",
        (35, 36),
        "BASE STATE SUPPORT",
        -1,
        "FY2019-20 base less the FY2020-21 reduction (58% cut, backfilled with federal CRF).",
    ),
    FundingSource(
        "FY 2021-22",
        "fy2022-23_hedbrf.pdf",
        "https://leg.colorado.gov/sites/default/files/fy2022-23_hedbrf.pdf",
        (27,),
        "TABLE 1",
        0,
        "FY2021-22 appropriation plus annualizations, JBC FY2022-23 briefing Table 1.",
    ),
    FundingSource(
        "FY 2022-23",
        "fy2023-24_hedbrf.pdf",
        JBC + "fy2023-24_hedbrf.pdf",
        (30,),
        "TABLE 1",
        0,
        "FY2022-23 appropriation plus annualizations, JBC FY2023-24 briefing Table 1.",
    ),
    FundingSource(
        "FY 2023-24",
        "fy2024-25_hedbrf1.pdf",
        JBC + "fy2024-25_hedbrf1.pdf",
        (35, 36),
        "TABLE 1",
        0,
        "FY2023-24 appropriation, JBC FY2024-25 briefing Table 1.",
    ),
    FundingSource(
        "FY 2024-25",
        "hedainfo-09-09-2025.pdf",
        JBC + "hedainfo-09-09-2025.pdf",
        (1, 2),
        "Enacted Long Bill Formula",
        0,
        "FY2024-25 base in the JBC staff memo on FY2025-26 appropriations (Aug. 27, 2025).",
    ),
    FundingSource(
        "FY 2025-26",
        "hedainfo-09-09-2025.pdf",
        JBC + "hedainfo-09-09-2025.pdf",
        (1, 2),
        "Enacted Long Bill Formula",
        1,
        "FY2025-26 enacted Long Bill formula amount (before a $9.5M mid-year supplemental cut).",
    ),
]

# Federal Coronavirus Relief Fund backfill by board ($450M; allocated in late
# FY2019-20, $429.2M of it spent in FY2020-21). JBC FY2021-22 briefing, p.10.
CRF_SOURCE = FundingSource(
    "FY 2020-21",
    "fy2021-22_hedbrf.pdf",
    JBC + "fy2021-22_hedbrf.pdf",
    (9, 10),
    "CORONAVIRUS",
    3,
    "Federal Coronavirus Relief Fund allocation by governing board.",
)

CPI_SERIES = "CUURS48BSA0"
CPI_URL = "https://download.bls.gov/pub/time.series/cu/cu.data.1.AllItems"
CPI_BASE_YEAR = "FY 2025-26"

MARKERS = [
    {"fy": "FY 2015-16", "label": "Graduate FTE redefined (24 credit hours)", "kind": "fte"},
    {"fy": "FY 2020-21", "label": "COVID cut, federal backfill", "kind": "funding"},
    {"fy": "FY 2021-22", "label": "HB 20-1366 model first used", "kind": "policy"},
    {"fy": "FY 2027-28", "label": "HB 26-1345 results-informed funding", "kind": "policy"},
]

NUM = r"\(?\$?-?[\d,]*\d\)?"


# ── Pure parsers (tested offline) ────────────────────────────────────────────
def to_int(token: str) -> int:
    """Parse ``$1,234`` / ``(1,234)`` accounting-style numbers."""
    value = int(re.sub(r"[^\d]", "", token))
    return -value if token.startswith("(") or "-" in token else value


def parse_fte_text(text: str) -> tuple[list[str], dict[str, list[int]], dict[str, list[int]]]:
    """Parse one CDHE FTE report.

    Returns ``(fiscal_years, institutions, summaries)`` where institutions maps
    the report's row label to one value per fiscal year and summaries holds the
    report's own board/public totals for validation.
    """
    years = [f"FY {a}-{b}" for a, b in re.findall(r"FY (\d{4})-(\d{2})", text)]
    seen: list[str] = []
    for y in years:
        if y not in seen:
            seen.append(y)
    years = seen
    n = len(years)
    rows: dict[str, list[int]] = {}
    summaries: dict[str, list[int]] = {}
    row_re = re.compile(rf"^(?P<label>[A-Za-z][^\d]*?)\s+(?P<nums>(?:{NUM}\s*){{{n},{n + 1}}})$")
    for raw in text.splitlines():
        line = raw.strip()
        m = row_re.match(line)
        if not m or line.startswith("FY "):
            continue
        label = m["label"].strip()
        tokens = m["nums"].split()
        if len(tokens) == n + 1:
            # Some reports print the leading digit of the first column as a
            # separate glyph ("1 6,096" for 16,096); rejoin it.
            if not re.fullmatch(r"\d", tokens[0]):
                continue
            tokens = [tokens[0] + tokens[1], *tokens[2:]]
        values = [to_int(t) for t in tokens]
        if label.endswith(":") or label.endswith("Summary"):
            summaries[label.rstrip(":")] = values
        else:
            rows[label] = values
    return years, rows, summaries


def canonical_institution(label: str) -> tuple[str, str, int] | None:
    """Map a report row label to ``(canonical name, board, UNITID)``."""
    for name, board, unitid, pattern in INSTITUTIONS:
        if re.search(pattern, label):
            return name, board, unitid
    return None


def parse_board_rows(text: str, marker: str) -> dict[str, list[int]]:
    """Return the numbers on the first row per governing board after ``marker``.

    Handles JBC tables where a label wraps ("Colorado Mesa" / "University ...")
    by joining a numberless line onto the next one.
    """
    start = text.find(marker)
    body = text[start:] if start >= 0 else text
    out: dict[str, list[int]] = {}
    previous = ""
    for raw in body.splitlines():
        line = raw.strip()
        nums = re.findall(r"\(?\$?-?\d{1,3}(?:,\d{3})+\)?", line)
        if not nums:
            previous = line
            continue
        for bid, _, pattern in BOARDS:
            if bid in out:
                continue
            if re.search(pattern, line) or (previous and re.search(pattern, previous + " " + line)):
                out[bid] = [to_int(t) for t in nums]
                break
        previous = ""
    return out


def pick(values: list[int], column: int) -> int:
    return values[0] + values[1] if column == -1 else values[column]


def fiscal_year_cpi(lines: list[str], series: str = CPI_SERIES) -> dict[str, float]:
    """Average a BLS bimonthly/monthly CPI series over July-June fiscal years."""
    by_fy: dict[str, list[float]] = {}
    for ln in lines:
        parts = ln.split()
        if len(parts) < 4 or parts[0] != series or not parts[2].startswith("M"):
            continue
        year, month = int(parts[1]), int(parts[2][1:])
        if month == 13:  # annual average row
            continue
        start = year if month >= 7 else year - 1
        fy = f"FY {start}-{str(start + 1)[2:]}"
        by_fy.setdefault(fy, []).append(float(parts[3]))
    # Require a full fiscal year of observations (6 bimonthly or 12 monthly).
    return {fy: round(sum(v) / len(v), 3) for fy, v in by_fy.items() if len(v) in (6, 12)}


def per_fte(funding: float | None, fte: float | None) -> int | None:
    if not funding or not fte:
        return None
    return round(funding / fte)


# ── I/O ──────────────────────────────────────────────────────────────────────
def _download(url: str, path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            path.write_bytes(resp.read())
    return path


def _pdf_text(path: Path, pages: tuple[int, ...] | None = None) -> str:
    import pdfplumber  # optional dependency, only needed to rebuild

    with pdfplumber.open(path) as pdf:
        chosen = [pdf.pages[i] for i in pages] if pages else pdf.pages
        return "\n".join(p.extract_text() or "" for p in chosen)


def load_fte(raw_dir: Path = RAW_DIR) -> tuple[list[str], dict[str, dict]]:
    """Merge both vintages of the three FTE series into one panel per institution."""
    all_years: list[str] = []
    inst: dict[str, dict] = {}
    for key, series in FTE_SERIES.items():
        for vintage in FTE_VINTAGES:
            path = _download(
                FTE_URL.format(s=series, v=vintage), raw_dir / f"hed{series}_{vintage}.pdf"
            )
            years, rows, summaries = parse_fte_text(_pdf_text(path))
            check_summaries(rows, summaries, path.name)
            for y in years:
                if y not in all_years:
                    all_years.append(y)
            for label, values in rows.items():
                hit = canonical_institution(label)
                if hit is None:
                    raise ValueError(f"Unmapped institution {label!r} in {path.name}")
                name, board, unitid = hit
                rec = inst.setdefault(
                    name, {"name": name, "board": board, "unitid": unitid, "series": {}}
                )
                target = rec["series"].setdefault(key, {})
                for y, v in zip(years, values):
                    if y in target and target[y] != v:
                        raise ValueError(f"{name} {key} {y}: vintages disagree")
                    target[y] = v
    all_years.sort()
    return all_years, inst


def check_summaries(
    rows: dict[str, list[int]], summaries: dict[str, list[int]], src: str, tolerance: int = 5
) -> None:
    """The institution rows must add up to the report's own public total.

    The published rows are rounded to whole FTE, so sums may miss the printed
    total by a couple of FTE; anything beyond ``tolerance`` is a parse error.
    """
    public = summaries.get("Public Summary")
    if public is None:
        return
    total = [sum(col) for col in zip(*rows.values())]
    if len(total) != len(public) or any(abs(a - b) > tolerance for a, b in zip(total, public)):
        raise ValueError(f"{src}: institution rows {total} != Public Summary {public}")


def load_funding(raw_dir: Path = RAW_DIR) -> dict[str, dict[str, dict]]:
    """Return ``{board: {fiscal_year: {"value", "source"}}}`` from the JBC tables."""
    out: dict[str, dict[str, dict]] = {b: {} for b in BOARD_IDS}
    for src in FUNDING_SOURCES:
        path = _download(src.url, raw_dir / src.file)
        rows = parse_board_rows(_pdf_text(path, src.pages), src.marker)
        missing = set(BOARD_IDS) - set(rows)
        if missing:
            raise ValueError(f"{src.file}: no rows for {sorted(missing)}")
        for bid, values in rows.items():
            out[bid][src.fiscal_year] = {"value": pick(values, src.column), "source": src.cite}
    return out


def load_crf(raw_dir: Path = RAW_DIR) -> dict[str, int]:
    path = _download(CRF_SOURCE.url, raw_dir / CRF_SOURCE.file)
    rows = parse_board_rows(_pdf_text(path, CRF_SOURCE.pages), CRF_SOURCE.marker)
    crf = {b: pick(v, CRF_SOURCE.column) for b, v in rows.items()}
    if sum(crf.values()) != 450_000_000:
        raise ValueError(f"CRF rows sum to {sum(crf.values()):,}, expected $450,000,000")
    return crf


def load_cpi(raw_dir: Path = RAW_DIR) -> dict[str, float]:
    path = _download(CPI_URL, raw_dir / "cu.data.1.AllItems.txt")
    return fiscal_year_cpi(path.read_text().splitlines())


def build(raw_dir: Path = RAW_DIR, out: Path = OUT) -> dict:
    fte_years, inst = load_fte(raw_dir)
    funding = load_funding(raw_dir)
    crf = load_crf(raw_dir)
    cpi = load_cpi(raw_dir)
    funding_years = [s.fiscal_year for s in FUNDING_SOURCES]
    deflator = {fy: round(cpi[CPI_BASE_YEAR] / cpi[fy], 5) for fy in funding_years}

    boards = []
    for bid, name, _ in BOARDS:
        members = [r for r in inst.values() if r["board"] == bid]
        fte = {
            key: [
                sum(m["series"].get(key, {}).get(y, 0) for m in members) or None for y in fte_years
            ]
            for key in FTE_SERIES
        }
        boards.append(
            {
                "id": bid,
                "name": name,
                "state": bid in STATE_BOARDS,
                "funding": [funding[bid][fy]["value"] for fy in funding_years],
                "fundingSource": [funding[bid][fy]["source"] for fy in funding_years],
                "crf": crf.get(bid),
                "fte": fte if members else None,
                "institutions": [m["name"] for m in members],
            }
        )

    payload = {
        "meta": {
            "built": date.today().isoformat(),
            "fteYears": fte_years,
            "fundingYears": funding_years,
            "deflator": deflator,
            "cpiSeries": CPI_SERIES,
            "cpiBase": CPI_BASE_YEAR,
            "markers": MARKERS,
            "sources": {
                "fte": "https://spl.cde.state.co.us/artemis/hedserials/",
                "fteReport": FTE_URL.format(s="1540", v="202425"),
                "funding": [s.cite for s in FUNDING_SOURCES],
                "crf": CRF_SOURCE.cite,
                "cpi": "https://www.bls.gov/regions/mountain-plains/co_denver_msa.htm",
                "formula": "https://cdhe.colorado.gov/colorado-higher-education-funding-formula",
                "metrics": "https://cdhe.colorado.gov/sites/highered/files/Colorado_Performance_Funding_Overview_and_Data_Definitions_2025_26_1.pdf",
                "hb1345": "https://leg.colorado.gov/bills/hb26-1345",
                "fy2627": JBC + "fy2026-27_hedbrf.pdf",
            },
        },
        "boards": boards,
        "institutions": [
            {
                "name": r["name"],
                "board": r["board"],
                "unitid": r["unitid"],
                **{k: [r["series"].get(k, {}).get(y) for y in fte_years] for k in FTE_SERIES},
            }
            for r in sorted(inst.values(), key=lambda r: (BOARD_IDS.index(r["board"]), r["name"]))
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    payload = build(args.raw_dir, args.out)
    total = sum(b["funding"][-1] for b in payload["boards"])
    print(
        f"Wrote {args.out}: {len(payload['institutions'])} institutions, "
        f"{len(payload['boards'])} boards, FY2025-26 formula total ${total:,}"
    )


if __name__ == "__main__":
    main()
