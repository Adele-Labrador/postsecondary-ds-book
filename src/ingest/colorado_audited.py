"""Latest audited-statement finances for the CU and CSU systems (FY 2024-25).

IPEDS Finance lags the fiscal year by about two years; the FY 2024-25 file is
not yet published. The governing boards' own annual financial reports are
newer, so this module reads them as a *separate layer*. It does not splice
them onto the IPEDS series. Both reports carry the prior year, so the layer
compares FY 2023-24 with FY 2024-25 from the same source.

Sources (all public PDFs, saved under ``data/raw/audited/``):

* **CU campus supplements** (``supplementalsfy2025.pdf``,
  ``supplementals-fy2024.pdf``). These are the University of Colorado's
  campus-level Statements of Revenues, Expenses, and Changes in Net Position
  (SRECNP), broken out by fund. CU labels them *unaudited supplements* to
  the audited Annual Financial Report. The final ``FY 20xx`` column (after
  report adjustments) is read for Boulder, Colorado Springs,
  Denver | Anschutz, System Administration, and the consolidated total.
* **CSU System audited statements** (``finstmt2025.pdf``). These report the
  whole system (Fort Collins, Pueblo, CSU Global, and the system office),
  with no campus breakdown. The "University" column is read, which excludes
  the discretely presented foundations. The FY 2023-24 column is restated in
  the FY 2025 report.

The statements follow GASB 34/35. Pell grants, gifts, investment income, and
state appropriations are *nonoperating*. Colorado's College Opportunity Fund
stipends are booked as tuition, and fee-for-service contracts are shown
separately as operating revenue. Figures are not comparable line for line
with IPEDS F1A, which re-maps the same statements into survey categories.

Per-FTE values use IPEDS 12-month FTE (``EFIA2024`` for FY 2023-24 and
``EFIA2025`` for FY 2024-25; FTEUG + FTEGD), the same convention as
:mod:`src.ingest.colorado_finance`.

Usage (from the repository root; needs ``pdfplumber``)::

    python -m src.ingest.colorado_audited
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.ingest.build_dashboard_data_nces import RAW_DIR as NCES_RAW
from src.ingest.build_dashboard_data_nces import fetch_component
from src.ingest.colorado import _download

RAW = Path("data/raw/audited")
OUT = Path("dashboard/data/colorado_audited.json")
YEARS = ["FY 2023-24", "FY 2024-25"]

SOURCES = {
    "cu2025": {
        "file": "cu_supp_fy2025.pdf",
        "url": "https://www.cu.edu/doc/supplementalsfy2025pdf?download=true",
        "title": "University of Colorado, Unaudited Supplement to the Annual "
        "Financial Report, June 30, 2025",
    },
    "cu2024": {
        "file": "cu_supp_fy2024.pdf",
        "url": "https://www.cu.edu/doc/supplementals-fy2024pdf-1",
        "title": "University of Colorado, Unaudited Supplement to the Annual "
        "Financial Report, June 30, 2024",
    },
    "cuafr": {
        "file": "cu_afr_fy2025.pdf",
        "url": "https://www.cu.edu/doc/2025-university-colorado-afrpdf?download=true",
        "title": "University of Colorado, FY 2025 Annual Financial Report (audited)",
    },
    "csu": {
        "file": "csu_fs_fy2025.pdf",
        "url": "https://busfin.colostate.edu/Forms/Fin_Statements/finstmt2025.pdf",
        "title": "Colorado State University System, Financial Statements, "
        "June 30, 2025 and 2024 (audited)",
    },
}
LISTING = {
    "cu": "https://www.cu.edu/controller/accounting-finance/external-reporting/supplementals",
    "csu": "https://busfin.colostate.edu/resources/Fin_Statements.aspx",
}

# CU supplement: measure -> (row label, occurrence, required). The label is
# matched against the end of the row's description text.
CU_ROWS: dict[str, tuple[str, str, bool]] = {
    "tuitionGross": ("STUDENT TUITION", "first", False),
    "tuitionNet": ("STUDENT TUITION, NET", "last", False),
    "feesGross": ("STUDENT FEES", "first", False),
    "feesNet": ("STUDENT FEES, NET", "last", False),
    "feeForService": ("FEE-FOR-SERVICE CONTRACTS", "last", False),
    "grantsFederal": ("FEDERAL GRANTS AND CONTRACTS", "last", False),
    "grantsStateLocal": ("STATE AND LOCAL GRANTS AND CONTRACTS", "last", False),
    "grantsNongov": ("NONGOVERNMENTAL GRANTS AND CONTRACTS", "last", False),
    "salesServices": ("SALES AND SERVICES OF EDUCATIONAL DEPARTMENTS", "last", False),
    "auxiliaryRevenue": ("AUXILIARY ENTERPRISES, NET", "last", False),
    "healthRevenue": ("HEALTH SERVICES OPERATING REVENUES", "last", False),
    "internalRevenue": ("INTERNAL REVENUES", "last", False),
    "otherOperatingRows": ("OTHER OPERATING REVENUES", "last", False),
    "operatingRevenue": ("TOTAL OPERATING REVENUES", "last", True),
    "instruction": ("INSTRUCTION", "last", False),
    "research": ("RESEARCH", "last", False),
    "publicService": ("PUBLIC SERVICE", "last", False),
    "academicSupport": ("ACADEMIC SUPPORT", "last", False),
    "studentServices": ("STUDENT SERVICES", "last", False),
    "institutionalSupport": ("INSTITUTIONAL SUPPORT", "last", False),
    "operationMaintenance": ("OPERATION AND MAINTENANCE OF PLANT", "last", False),
    "scholarships": ("STUDENT AID", "last", False),
    "depreciation": ("DEPRECIATION AND AMORTIZATION", "last", False),
    "auxiliaryExpense": ("AUXILIARY ENTERPRISES", "last", False),
    "healthServices": ("HEALTH SERVICES OPERATING EXPENSES", "last", False),
    "otherExpenseRows": ("OTHER OPERATING EXPENSES", "last", False),
    "operatingExpense": ("TOTAL OPERATING EXPENSES", "last", True),
    "pell": ("FEDERAL PELL GRANT", "first", False),
    "stateAppropriations": ("STATE APPROPRIATIONS", "first", False),
    "gifts": ("GIFTS", "first", False),
    "investment": ("INVESTMENT INCOME (LOSS), NET", "last", False),
    "interest": ("INTEREST ON CAPITAL ASSET RELATED DEBT", "last", False),
    "nonoperating": ("TOTAL NONOPERATING REVENUES, NET", "last", True),
    "otherRevenues": ("TOTAL OTHER REVENUES", "last", False),
    "changeInNetPosition": ("CHANGE IN NET POSITION", "last", False),
}

CU_CAMPUSES = {
    "Consolidated": "cu",
    "Boulder": "cub",
    "Colorado Springs": "uccs",
    "Denver│Anschutz": "ucd",
    "System": "cusys",
}

# CSU audited SRECNP (thousands): measure -> line prefix on pp. 27-28.
CSU_ROWS: dict[str, str] = {
    "tuitionNet": "",
    "feeForService": "State fee for service revenue",
    "grants": "respectively) (Note 13)",
    "salesServices": "Sales and services of educational activities",
    "auxiliaryRevenue": "",
    "otherOperating": "Other revenues",
    "operatingRevenue": "Total Operating Revenues",
    "instruction": "Instruction",
    "research": "Research",
    "publicService": "Public service",
    "academicSupport": "Academic support",
    "studentServices": "Student services",
    "institutionalSupport": "Institutional support",
    "operationMaintenance": "Operation and maintenance of plant",
    "scholarships": "Scholarships and fellowships",
    "auxiliaryExpense": "Auxiliary enterprises",
    "depreciation": "Depreciation/Amortization",
    "operatingExpense": "Total Operating Expenses",
    "stateAppropriations": "State appropriations",
    "gifts": "Gifts",
    "investment": "pledged for bonds in 2025 and 2024, respectively) (Note 13)",
    "interest": "Interest expense on capital debt",
    "pell": "revenues pledged for bonds in 2025 and 2024, respectively) (Note 13)",
    "nonoperating": "Total Nonoperating Revenues",
    "otherRevenues": "Total Other Revenues",
    "changeInNetPosition": "Change in net position",
}
# Scholarship allowances on tuition and fees, stated in the tuition caption.
CSU_ALLOWANCE = re.compile(r"net of scholarship allowances of \$([\d,]+) and\s*\$([\d,]+) for 2025")

NUMERIC_FRAGMENT = re.compile(r"^[(\-]?[\d,.]*\)?$")
NUM = re.compile(r"^\(?-?[\d,]+(\.\d+)?\)?$|^-$")


def parse_amount(text: str) -> float:
    """Parse a statement amount: ``1,234.50``, ``(1,234.50)``, ``-1,234``, or ``-``."""
    t = text.replace(" ", "").replace("$", "")
    if t in ("", "-"):
        return 0.0
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-")
    value = float(t.strip("()-").replace(",", ""))
    return -value if neg else value


def _rows(words: list[dict], tol: float = 1.5) -> list[dict]:
    """Cluster words into rows by their top coordinate."""
    rows: list[dict] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(rows[-1]["top"] - w["top"]) <= tol:
            rows[-1]["words"].append(w)
        else:
            rows.append({"top": w["top"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
    return rows


def clean_label(text: str) -> str:
    return re.sub(r"\s*\(PLEDGED REVENUES OF [^)]*\)", "", text).strip()


def page_values(
    words: list[dict], label_max_x: float = 345, group_x: float = 100
) -> list[tuple[str, float]]:
    """Return ``(label, value)`` pairs, in page order, for one supplement page.

    The value is the final column (``FY 20xx``). Labels sit in a description
    block on the left. Level-one group headings (``x0 < group_x``) are dropped
    unless they are totals, because some pages print a group heading on the
    value's line and the row label a few points below it. Each value row is
    then paired with the nearest label row.
    """
    fy = [w for w in words if w["text"] == "FY"]
    if not fy:
        return []
    col = max(w["x0"] for w in fy) - 15
    header = max(w["top"] for w in fy)
    values = []
    for r in _rows([w for w in words if w["x0"] >= col and w["top"] > header + 2]):
        text = "".join(w["text"] for w in r["words"])
        if NUM.match(text.replace(" ", "")):
            values.append((r["top"], parse_amount(text)))
    labels = []

    def is_label(w: dict) -> bool:
        return (
            w["x1"] < label_max_x
            and w["top"] > header + 2
            and not NUMERIC_FRAGMENT.match(w["text"])
        )

    for r in _rows([w for w in words if is_label(w)]):
        full = " ".join(w["text"] for w in r["words"])
        # Drop a level-one heading: the run of words starting left of
        # ``group_x`` and continuing with normal word spacing.
        keep, heading, prev = [], False, None
        for w in r["words"]:
            if prev is None and w["x0"] < group_x:
                heading = True
            elif heading and prev is not None and w["x0"] - prev["x1"] > 3:
                heading = False
            if not heading:
                keep.append(w["text"])
            prev = w
        if full.startswith(("TOTAL", "OPERATING, NET", "CHANGE IN NET POSITION")):
            text = full
        elif keep:
            text = " ".join(keep)
        else:
            continue
        labels.append({"top": r["top"], "text": clean_label(text), "value": None, "dist": 99.0})
    for top, value in values:
        if not labels:
            break
        best = min(labels, key=lambda lab: abs(lab["top"] - top))
        d = abs(best["top"] - top)
        if d <= 9 and d < best["dist"]:
            best["value"], best["dist"] = value, d
    return [(lab["text"], lab["value"]) for lab in labels if lab["value"] is not None]


def pick(pairs: list[tuple[str, float]], label: str, occurrence: str) -> float | None:
    hits = [v for t, v in pairs if t == label or t.endswith(" " + label)]
    if not hits:
        return None
    return hits[0] if occurrence == "first" else hits[-1]


def extract_cu(pairs: list[tuple[str, float]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, (label, occ, required) in CU_ROWS.items():
        v = pick(pairs, label, occ)
        if v is None:
            if required:
                raise ValueError(f"CU supplement row not found: {label}")
            v = 0.0
        out[key] = v
    # Allowance = gross minus net, on tuition and fees together.
    out["allowance"] = (out["tuitionGross"] + out["feesGross"]) - (
        out["tuitionNet"] + out["feesNet"]
    )
    out["tuitionFeesGross"] = out["tuitionGross"] + out["feesGross"]
    out["tuitionFeesNet"] = out["tuitionNet"] + out["feesNet"]
    out["grants"] = out["grantsFederal"] + out["grantsStateLocal"] + out["grantsNongov"]
    # "Other operating" is total operating revenue minus the named lines. The
    # printed rows are kept for a reconciliation note, because at least one
    # supplement (UCB FY 2024) prints a final-column group total that is
    # twice its own subtotal and does not tie to total operating revenue.
    out["healthServicesRevenue"] = out["healthRevenue"]
    printed = out.pop("healthRevenue") + out.pop("internalRevenue") + out.pop("otherOperatingRows")
    named = (
        out["tuitionNet"]
        + out["feesNet"]
        + out["feeForService"]
        + out["salesServices"]
        + out["auxiliaryRevenue"]
    )
    named += out["grantsFederal"] + out["grantsStateLocal"] + out["grantsNongov"]
    out["otherOperating"] = out["operatingRevenue"] - named
    out["otherOperatingPrinted"] = printed
    out["otherExpense"] = out.pop("otherExpenseRows")
    out["operatingIncome"] = out["operatingRevenue"] - out["operatingExpense"]
    out["beforeOther"] = out["operatingIncome"] + out["nonoperating"]
    out["interest"] = -abs(out["interest"])
    return out


def read_cu_supplement(path: Path) -> dict[str, dict[str, float]]:
    """Read the campus SRECNP pages (plus their nonoperating continuation)."""
    import pdfplumber

    found: dict[str, dict[str, float]] = {}
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages
        for i, page in enumerate(pages):
            head = (page.extract_text() or "").split("\n")[:6]
            if not any("STATEMENT OF REVENUES, EXPENSES" in h for h in head):
                continue
            if any("Auxiliary and Self" in h for h in head):
                continue
            campus = next((CU_CAMPUSES[h.strip()] for h in head if h.strip() in CU_CAMPUSES), None)
            if campus is None:
                continue
            pairs = page_values(page.extract_words())
            if i + 1 < len(pages):
                pairs += page_values(pages[i + 1].extract_words())
            found[campus] = extract_cu(pairs)
            if campus != "cu":
                # Campus statements continue into CU-internal transfers; only
                # the consolidated bottom line is shown.
                found[campus]["changeInNetPosition"] = None
    missing = set(CU_CAMPUSES.values()) - set(found)
    if missing:
        raise ValueError(f"{path.name}: missing campus statements {sorted(missing)}")
    return found


def csu_line(lines: list[str], prefix: str) -> tuple[float, float]:
    """Return (FY2025, FY2024) University-column values for a CSU SRECNP line."""
    for line in lines:
        if line.startswith(prefix):
            rest = re.sub(r"\(Notes? [^)]*\)", " ", line[len(prefix) :]).replace("$", " ")
            if rest and not rest[0].isspace():
                continue  # e.g. "Auxiliary enterprises, (including ..." caption
            tokens = [
                t
                for t in rest.split()
                if NUM.match(t) and (t == "-" or any(c.isdigit() for c in t))
            ]
            if len(tokens) >= 3:
                return parse_amount(tokens[0]) * 1000, parse_amount(tokens[2]) * 1000
    raise ValueError(f"CSU line not found: {prefix}")


CU_PARTS = ("cub", "uccs", "ucd", "cusys")


def reconcile_cu(
    year: dict[str, dict[str, float]], label: str, tolerance: float = 5.0
) -> list[str]:
    """Tie campus nonoperating totals to the consolidated statement.

    The campus columns add to CU consolidated except for internal service
    center eliminations, which net out between operating revenue and expense.
    Nonoperating totals must add exactly. If one campus is off by exactly twice
    its own value, its final column printed the wrong sign (UCCS FY 2024
    prints "(18,017,602.56)" beside a positive fund subtotal); the sign is
    corrected and noted.
    """
    notes = []
    gap = year["cu"]["nonoperating"] - sum(year[c]["nonoperating"] for c in CU_PARTS)
    if abs(gap) > tolerance:
        fixed = False
        for c in CU_PARTS:
            if abs(gap - (-2 * year[c]["nonoperating"])) <= tolerance:
                year[c]["nonoperating"] *= -1
                year[c]["beforeOther"] = year[c]["operatingIncome"] + year[c]["nonoperating"]
                name = {e[0]: e[1] for e in ENTITIES}.get(c, c)
                notes.append(
                    f"{name} {label}: total nonoperating printed with the wrong sign in the supplement's final "
                    f"column; corrected to {year[c]['nonoperating']:,.2f} so campuses tie to CU consolidated."
                )
                fixed = True
                break
        if not fixed:
            raise ValueError(
                f"CU {label}: campus nonoperating totals miss consolidated by {gap:,.2f}"
            )
    elim = year["cu"]["operatingRevenue"] - sum(year[c]["operatingRevenue"] for c in CU_PARTS)
    elim_exp = year["cu"]["operatingExpense"] - sum(year[c]["operatingExpense"] for c in CU_PARTS)
    if abs(elim - elim_exp) > tolerance:
        raise ValueError(
            f"CU {label}: operating eliminations do not net ({elim:,.2f} vs {elim_exp:,.2f})"
        )
    return notes


def read_csu(text: str) -> dict[str, dict[str, float]]:
    pages = text.split("\f")
    stmt = [
        p for p in pages if "Statements of Revenues, Expenses, and Changes in Net Position" in p
    ]
    stmt = [p for p in stmt if "(Amounts expressed in thousands)" in p and "University Units" in p]
    if len(stmt) < 2:
        raise ValueError("CSU SRECNP pages not found")
    lines = [ln.strip() for p in stmt[:2] for ln in p.split("\n")]
    # The Grants and Pell lines share a caption tail; disambiguate by order.
    grant_lines = [ln for ln in lines if ln.startswith("respectively) (Note 13)")]
    pledged = [
        ln
        for ln in lines
        if ln.startswith("pledged for bonds in 2025 and 2024, respectively) (Note 13)")
    ]
    pell_lines = [
        ln
        for ln in lines
        if ln.startswith("revenues pledged for bonds in 2025 and 2024, respectively) (Note 13)")
    ]
    # Tuition and auxiliary captions end on lines like
    # "$153,418 for 2025 and 2024, respectively) (Note 13, 21) $ 644,934 - ...".
    caption = [ln for ln in lines if "for 2025 and 2024, respectively) (Note 13, 21)" in ln]
    if len(caption) < 2:
        raise ValueError("CSU tuition/auxiliary caption lines not found")
    tail = "respectively) (Note 13, 21)"
    caption = [ln[ln.index(tail) :] for ln in caption[:2]]
    y25: dict[str, float] = {}
    y24: dict[str, float] = {}
    for key, prefix in CSU_ROWS.items():
        pool = {"grants": grant_lines, "investment": pledged, "pell": pell_lines}.get(key, lines)
        if key in ("tuitionNet", "auxiliaryRevenue"):
            pool, prefix = [caption[0 if key == "tuitionNet" else 1]], tail
        a, b = csu_line(pool, prefix)
        y25[key], y24[key] = a, b
    m = CSU_ALLOWANCE.search(" ".join(lines))
    if not m:
        raise ValueError("CSU scholarship allowance caption not found")
    for d, raw in ((y25, m.group(1)), (y24, m.group(2))):
        d["allowance"] = parse_amount(raw) * 1000
        d["otherExpense"] = 0.0
        d["healthServices"] = 0.0
        d["healthServicesRevenue"] = 0.0
        d["tuitionFeesNet"] = d.pop("tuitionNet")
        d["tuitionFeesGross"] = d["tuitionFeesNet"] + d["allowance"]
        d["operatingIncome"] = d["operatingRevenue"] - d["operatingExpense"]
        d["beforeOther"] = d["operatingIncome"] + d["nonoperating"]
    return {"FY 2024-25": y25, "FY 2023-24": y24}


REVENUE_PARTS = (
    "tuitionFeesNet",
    "feeForService",
    "grants",
    "salesServices",
    "auxiliaryRevenue",
    "otherOperating",
)
EXPENSE_PARTS = (
    "instruction",
    "research",
    "publicService",
    "academicSupport",
    "studentServices",
    "institutionalSupport",
    "operationMaintenance",
    "scholarships",
    "auxiliaryExpense",
    "depreciation",
    "healthServices",
    "otherExpense",
)


def check(values: dict[str, float], name: str, tolerance: float = 1500.0) -> str | None:
    """Components must add to the statement totals (tolerance in dollars).

    Returns a reconciliation note when a printed "other operating" row
    disagrees with the residual, otherwise ``None``.
    """
    rev = sum(values[k] for k in REVENUE_PARTS)
    exp = sum(values[k] for k in EXPENSE_PARTS)
    if abs(rev - values["operatingRevenue"]) > tolerance:
        raise ValueError(
            f"{name}: revenue parts {rev:,.0f} != total {values['operatingRevenue']:,.0f}"
        )
    if abs(exp - values["operatingExpense"]) > tolerance:
        raise ValueError(
            f"{name}: expense parts {exp:,.0f} != total {values['operatingExpense']:,.0f}"
        )
    if values["otherOperating"] < -tolerance:
        raise ValueError(f"{name}: negative residual other operating revenue")
    printed = values.get("otherOperatingPrinted")
    if printed is not None and abs(printed - values["otherOperating"]) > tolerance:
        return (
            f"{name}: printed other operating revenue {printed:,.2f} does not tie to total "
            f"operating revenue; the reconciling residual {values['otherOperating']:,.2f} is used."
        )
    return None


FTE_UNITS = {
    "cub": [126614],
    "uccs": [126580],
    "ucd": [126562],
    "cu": [126614, 126580, 126562],
    "csu": [126818, 128106, 476975],
}
ENTITIES = [
    ("cub", "CU Boulder", "CU", "campus", "cu"),
    ("uccs", "UCCS", "CU", "campus", "cu"),
    ("ucd", "CU Denver | Anschutz", "CU", "campus", "cu"),
    ("cusys", "CU System Administration", "CU", "office", "cu"),
    ("cu", "CU (all campuses)", "CU", "system", "cu"),
    ("csu", "CSU System", "CSU", "system", "csu"),
]


def load_fte(nces_dir: Path = NCES_RAW) -> dict[str, dict[int, float]]:
    out = {}
    for label, stem in zip(YEARS, ("EFIA2024", "EFIA2025"), strict=True):
        frame = fetch_component(stem, nces_dir)
        frame.columns = [c.upper() for c in frame.columns]
        out[label] = {
            int(uid): float(sum(frame.loc[uid, c] for c in ("FTEUG", "FTEGD")))
            for uid in {u for units in FTE_UNITS.values() for u in units}
            if uid in frame.index
        }
    return out


def ensure_raw(raw: Path = RAW) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    for src in SOURCES.values():
        target = raw / src["file"]
        if not target.exists():
            _download(src["url"], target)


def build(raw: Path = RAW, nces_dir: Path = NCES_RAW, out: Path = OUT) -> dict:
    import pdfplumber

    ensure_raw(raw)
    cu = {
        "FY 2023-24": read_cu_supplement(raw / SOURCES["cu2024"]["file"]),
        "FY 2024-25": read_cu_supplement(raw / SOURCES["cu2025"]["file"]),
    }
    with pdfplumber.open(raw / SOURCES["csu"]["file"]) as pdf:
        csu_text = "\f".join(p.extract_text() or "" for p in pdf.pages)
    csu = read_csu(csu_text)
    quirks = []
    for y in YEARS:
        quirks += reconcile_cu(cu[y], y)
    fte = load_fte(nces_dir)

    entities = []
    for eid, name, board, scope, src in ENTITIES:
        by_year = {y: (cu[y][eid] if src == "cu" else csu[y]) for y in YEARS}
        for y in YEARS:
            note = check(by_year[y], f"{name} {y}")
            if note:
                quirks.append(note)
            by_year[y].pop("otherOperatingPrinted", None)
        keys = sorted(by_year[YEARS[1]])
        values = {
            k: [None if by_year[y].get(k) is None else round(by_year[y][k]) for y in YEARS]
            for k in keys
        }
        units = FTE_UNITS.get(eid)
        entity_fte = None
        if units:
            entity_fte = [round(sum(fte[y].get(u, 0.0) for u in units)) for y in YEARS]
        entities.append(
            {
                "id": eid,
                "name": name,
                "board": board,
                "scope": scope,
                "source": src,
                "unitids": units or [],
                "fte": entity_fte,
                "values": values,
            }
        )

    data = {
        "meta": {
            "years": YEARS,
            "units": "dollars (nominal)",
            "fteSource": "IPEDS 12-month FTE, EFIA2024 and EFIA2025 (FTEUG + FTEGD)",
            "restated": {"csu": ["FY 2023-24"]},
            "sources": SOURCES,
            "listing": LISTING,
            "pages": {
                "cu": "Supplement SRECNP pages: Consolidated CU-4/5, UCB-4/5, UCCS-4/5, UCD-4/5, SYS-4/5",
                "csu": "Statements of Revenues, Expenses, and Changes in Net Position, pp. 24-25 "
                "(PDF pp. 27-28); scholarship allowance in the tuition caption; COF stipends in Note 23",
            },
            "reconciliation": quirks,
            "notes": [
                "GASB business-type statements. Pell, gifts, investment income, and state "
                "appropriations are nonoperating; COF stipends are inside tuition.",
                "CU campus figures come from CU's unaudited campus supplement, which breaks "
                "out the audited statements; campus results stop before CU-internal transfers.",
                "CSU is system-wide (Fort Collins, Pueblo, CSU Global, system office); "
                "foundations (component units) are excluded. FY 2023-24 is restated.",
                "Not comparable line for line with IPEDS F1A.",
            ],
        },
        "entities": entities,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    return data


def main() -> None:
    data = build()
    for e in data["entities"]:
        v = e["values"]
        print(
            f"{e['name']:<26} opRev {v['operatingRevenue'][1] / 1e6:>9,.1f}M  "
            f"opExp {v['operatingExpense'][1] / 1e6:>9,.1f}M  fte {e['fte']}"
        )


if __name__ == "__main__":
    main()
