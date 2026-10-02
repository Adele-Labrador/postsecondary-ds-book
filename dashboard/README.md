# IPEDS Explorer — interactive dashboard

Live at <https://adele-labrador.github.io/postsecondary-ds-book/>, redeployed
by `.github/workflows/pages.yml` on every push that touches `dashboard/`.

A static, dependency-light dashboard built on the same IPEDS panel the book's
modules produce. It is the visual companion to `src/` : the peer-group logic
mirrors `src/features/peer_groups.py`, and the FTE forecast mirrors the
descriptive-trend baseline in `src/models/forecast_enrollment.py`.

## Contents

| Path                           | Purpose                                                             |
| ------------------------------ | ------------------------------------------------------------------- |
| `index.html`                   | Markup and CDN dependencies (Chart.js, d3-array, d3-geo)            |
| `styles.css`                   | Design tokens, light/dark themes, layout                            |
| `app.js`                       | Data load, filtering, charts, map, table, detail drawer             |
| `data/institutions.json`       | 3,649 degree-granting institutions, 2024 primary year               |
| `data/us-states.json`          | Pre-projected Albers USA state outlines as SVG paths                |
| `colorado.html`, `colorado.js` | Colorado panel: formula funding and resident FTE by governing board |
| `data/colorado.json`           | 13 governing boards, 29 institutions, FY2007-08 to FY2025-26        |
| `data/colorado_finance.json`   | IPEDS finance + FTE for 27 Colorado units, FY2014-15 to FY2023-24   |
| `data/colorado_audited.json`   | Audited CU and CSU statement lines, FY2023-24 and FY2024-25         |

## Rebuilding the data

Both files are generated, not hand-edited. From the repository root:

```bash
python -m src.ingest.build_dashboard_data_nces --year 2024   # -> dashboard/data/institutions.json
python -m src.ingest.build_us_map                            # -> dashboard/data/us-states.json
```

`build_dashboard_data_nces.py` reads the [NCES IPEDS Complete Data
Files](https://nces.ed.gov/ipeds/use-the-data) directly and caches the ZIPs in
`data/raw/nces/` (`--refresh` re-downloads them). It prefers NCES's revised
(`_rv`) releases and records any component still in its provisional release in
`meta.provisional`, which the dashboard shows in the header and footer.

NCES moved the files in 2026 to `https://nces.ed.gov/ipeds/complete-data-files/`.
The builder tries that path first and falls back to the legacy
`/ipeds/datacenter/data/` path, which still answers for older years but serves
the original releases without later revisions. The first 2023 build used five
of those stale archives (`ADM2023`, `EF2023D`, `GR2023`, `SFA2223`, `EFIA2024`).
Rebuilding 2023 from the revised files changed 9–46 institutions per metric
and national FTE by −0.03%. The original `build_dashboard_data.py` reads the same collections through
the Urban Institute Education Data Portal and is kept as an independent check.

### Current vintage

| Metric group                                   | Year | NCES file             | Status           |
| ---------------------------------------------- | ---- | --------------------- | ---------------- |
| Directory, Carnegie 2021 basic classification  | 2024 | `HD2024`              | Final            |
| Student-to-faculty ratio, fall retention       | 2024 | `EF2024D`             | Provisional      |
| Admissions and yield                           | 2024 | `ADM2024`             | Provisional      |
| In-state and out-of-state tuition and fees     | 2024 | `COST1_2024`          | Provisional      |
| In-district tuition and fees (`TUITION1+FEE1`) | 2024 | `COST1_2024`          | Provisional      |
| Undergraduate 12-month FTE, 2013–2024 series   | 2024 | `EFIA2014`–`EFIA2025` | 2024 provisional |
| Graduation rate within 150% of normal time     | 2023 | `GR2024`              | Provisional      |
| Pell share and average Pell award              | 2023 | `SFA2324`             | Provisional      |

Years follow the start-of-academic-year convention used throughout the book,
so the 12-month enrollment file `EFIA2025` (2024–25) is labeled 2024. `GR2025`
and `SFA2425` are not published yet, so graduation rates and aid stay one year
behind. Starting with 2024–25, NCES moved tuition out of the fall
Institutional Characteristics file (`IC{Y}_AY`) into the new winter Cost
component (`COST1_{Y}`); the `TUITION*`/`FEE*` variables are unchanged. See the
[IPEDS data release schedule](https://nces.ed.gov/ipeds/survey-components/data-release-schedule)
for when the provisional files become final.

### College Scorecard earnings and debt

`src/ingest/scorecard.py` merges three outcome measures from the
[College Scorecard](https://collegescorecard.ed.gov/data/) "Most Recent
Institution-Level Data" file (June 10, 2026 release) by UNITID. The merge
matches 3,645 of the 3,649 institutions; `--no-scorecard` skips it.

| Field          | Scorecard variable | Cohort                                                               |
| -------------- | ------------------ | -------------------------------------------------------------------- |
| `earnings4yr`  | `MD_EARN_WNE_4YR`  | Completers of 2017–18 and 2018–19, earnings in 2022–23, 2024 dollars |
| `earnings10yr` | `MD_EARN_WNE_P10`  | Entrants of 2009–10 and 2010–11, earnings in 2020–21, 2022 dollars   |
| `gradDebt`     | `GRAD_DEBT_MDN`    | Completers entering repayment in FY2020–21                           |

The cohorts come from the data dictionary's `Most_Recent_Inst_Cohort_Map`
sheet. All three cover federal (Title IV) aid recipients only, and earnings
cover those working and not enrolled. The 10-year measure follows every
entrant, including those who never finished, so it reflects both completion
and labor-market outcomes. The 4-year measure covers completers only.
Earnings are not adjusted for regional cost of living or program mix.

**Shared campus values.** Scorecard reports earnings and debt for a whole
6-digit OPEID family, so a main campus and its branches carry identical values:
536 campuses in 132 families, including all 21 Penn State campuses. Each
family counts once in medians, charts, the map and benchmarks, on its main
campus (Scorecard `MAIN == 1`, else the largest by FTE). Branches show the
shared value in grey. After this rule, 2,956 institutions contribute 4-year
earnings, 2,947 contribute 10-year earnings, and 2,724 contribute debt.

Spot checks against the Scorecard API matched exactly for CU Boulder
($76,850 / $69,738 / $19,500), the University of Denver, and UC Berkeley.
Median debt clusters at round amounts: $27,000 (174 institutions) equals the
sum of the four annual Direct Loan limits for dependent undergraduates
($5,500 + $6,500 + $7,500 + $7,500).

### Colorado panel

`colorado.html` pairs Colorado Department of Higher Education (CDHE) resident
FTE with the Joint Budget Committee's formula funding by governing board.

```bash
pip install -e ".[colorado]"   # pdfplumber
python -m src.ingest.colorado  # reads PDFs in data/raw/cdhe/, writes data/colorado.json
```

The raw PDFs (CDHE FTE reports hed1538/1539/1540 and JBC briefings for
FY2021-22 through FY2026-27) are listed with URLs in `src/ingest/colorado.py`
and are gitignored. `tests/test_colorado.py` checks the parsers and pins the
built file to published totals: $850.3M (FY2019-20), $357.1M plus the $450M
federal Coronavirus Relief Fund backfill (FY2020-21), $1.298B (FY2025-26), and
resident FTE of 148,445 (FY2024-25).

#### Campus finances (IPEDS)

The "Campus finances · IPEDS" section adds revenue and spending per student
FTE for each public campus from the IPEDS Finance survey (GASB form F1A,
`F1415_F1A` to `F2324_F1A`) and 12-month enrollment (`EFIA2015` to
`EFIA2024`), downloaded from the
[IPEDS complete data files](https://nces.ed.gov/ipeds/use-the-data).

```bash
python -m src.ingest.colorado_finance  # writes data/colorado_finance.json
```

- FTE is `FTEUG + FTEGD`, the NCES convention for per-FTE finance measures.
- Revenue per FTE stacks net tuition and fees (F1B01), state operating grants,
  contracts and appropriations (F1B03 + F1B11 + F1B14), local appropriations
  (F1B12) and federal nonoperating grants (F1B13, mostly Pell).
- Colorado sends state money through College Opportunity Fund stipends, which
  campuses book as tuition, and fee-for-service contracts, booked as state
  grants and contracts. IPEDS therefore cannot isolate formula funding; use
  the CDHE and JBC charts above for that.
- Campuses in PERA carry large non-cash pension and OPEB accruals (GASB 68/75)
  in fringe benefits, which swing by tens of millions a year and sometimes go
  negative. The default trend view uses salaries and wages by function
  (F1C012, F1C052, F1C062); "Total incl. benefits" shows the full function
  totals.
- Real dollars use the semiannual Denver-Aurora-Lakewood CPI-U (BLS
  CUUSS48BSA0), because the monthly series has no values from 1987 to late 2017. Values are then carried to FY2025-26 dollars with the page's factor.
- IPEDS unit 126562 combines CU Denver and the Anschutz Medical Campus, and
  126818 includes CSU's veterinary school and state agencies, so their
  per-FTE figures are high. FY2023-24 is provisional until NCES issues the
  revised file.
- Revenue and spending per FTE measure resources, not cost or efficiency.

Caveats:

- CDHE FTE is state fiscal-year (July to June) FTE used by the funding formula,
  not the IPEDS 12-month FTE in the national explorer. Board totals sum
  institution rows and can differ from printed totals by 1 to 2 FTE.
- Funding is the formula base: stipends, fee-for-service contracts, specialty
  education and local district/area technical college grants. One-time funds
  and the FY2025-26 Auraria Higher Education Center line are excluded.
- The FY2020-21 federal backfill is shown as a separate hatched segment.
- Real dollars use the BLS Denver-Aurora-Lakewood CPI-U averaged over each
  fiscal year, in FY2025-26 dollars. A nominal toggle is available.
- CU and CSU per-FTE figures include specialty education (medical, veterinary,
  agricultural and forest services). Area technical colleges have no resident
  FTE series and are excluded from per-FTE.
- Deep links: `colorado.html#board=CU` focuses a board; `index.html#inst=126614`
  opens an institution profile.

### 2024 refresh checks

- Universe 3,688 → 3,649: 59 exits (39 for-profit, 19 nonprofit, 1 public;
  largest Eastern Gateway Community College, closed 2024) and 20 entries.
- Undergraduate FTE +4.4% nationally (+6.0% two-year, +4.1% four-year). The
  Clearinghouse reported fall 2024 undergraduate headcount +4.7%.
- Median average Pell award $4,989 → $5,397, in line with the $500 increase in
  the maximum award for 2023–24.
- Tuition: median +3.0%, and 31 institutions moved by more than 40%, against
  26 in the 2022→2023 IC-to-IC comparison. The switch to the Cost file did not
  shift values. Large moves are institution-reported, such as Bridgewater
  College's reset to $15,000.

### Validation

Before the 2023 refresh, the NCES builder was run for 2022 and compared with
the shipped Urban-portal file. The universe (3,716 institutions) and all 37,160
FTE series values matched exactly, as did names, locations, control, level,
student-to-faculty ratio, and retention. Every remaining difference traced to
one of these causes:

- **NCES revisions.** 40 admit rates and 10 Pell shares changed in NCES's
  revised files after the portal loaded the original release.
- **Two-year graduation rates.** The portal query returned only 4-year cohort
  rows, so 1,196 two-year colleges had no graduation rate. They now do.
- **Portal differences.** Penn State–Main Campus had no Carnegie class in the
  portal (NCES: R1), College of the Atlantic carried a different code (NCES:
  Baccalaureate, Arts & Sciences), and two institutions' reported $0 tuition was
  dropped as missing.

The Carnegie labels for codes 27–33 were later found to be off by one (the 2021
edition added a Special Focus Research Institutions category). That affected
both builds equally, so the comparison above did not catch it. It is fixed and
covered by `tests/test_carnegie_codes.py`. Before the fix, the dashboard's
Tribal filter listed "Other Special Focus" institutions, and the 35 tribal
colleges showed as unclassified.

#### Latest audited statements (CU and CSU)

IPEDS Finance lags about two years, so the "Latest audited statements" card
adds FY2024-25 from the institutions' own annual reports, kept separate from
the IPEDS card because GASB statement lines are not IPEDS F1A lines.

- CU: the [FY2025 campus supplement](https://www.cu.edu/doc/supplementalsfy2025pdf?download=true)
  and [FY2024 supplement](https://www.cu.edu/doc/supplementals-fy2024pdf-1)
  (unaudited campus breakouts that reconcile to audited totals), plus the
  [FY2025 Annual Financial Report](https://www.cu.edu/doc/2025-university-colorado-afrpdf?download=true)
  for consolidated totals.
- CSU: the [CSU System FY2025 financial statements](https://busfin.colostate.edu/Forms/Fin_Statements/finstmt2025.pdf)
  (with restated FY2024), reported only at system level.

Save the PDFs in `data/raw/audited/` (`cu_supp_fy2025.pdf`, `cu_supp_fy2024.pdf`,
`cu_afr_fy2025.pdf`, `csu_fs_fy2025.pdf`), then:

```bash
pip install -e ".[colorado]"          # pdfplumber
python -m src.ingest.colorado_audited  # writes data/colorado_audited.json
```

- The parser reads the statement of revenues, expenses and changes in net
  position by word position, and `check()` requires revenue and expense lines
  to sum to the printed totals. "Other operating" is the residual.
- Reconciliation fixes are listed in the JSON `meta.reconciliation` and on the
  card: UCCS FY2023-24 nonoperating total printed with the wrong sign, and
  UCB/UCCS FY2023-24 printed "other operating" lines that do not tie to total
  operating revenue.
- Campus operating lines include CU Denver internal service centers
  ($19.2M FY2023-24, $15.7M FY2024-25), which are eliminated in the
  consolidated statement.
- Per-FTE uses IPEDS 12-month FTE (EFIA2024, EFIA2025); the CU system office
  has no FTE, so only totals are shown for it.

#### How to read guide

The "How to read a university income statement" card walks through six steps
(sticker price → operating revenue → spending → operating loss →
nonoperating → compare fairly) on a waterfall built from the same audited
lines. Its text is computed from the JSON, so it updates when the data does.
Deep links: `#section=guide`, `#section=audited&aud=csu&audview=total`.

## Running locally

No build step. Serve the directory over HTTP (the JSON fetches need it):

```bash
cd dashboard && python3 -m http.server 8000
```

## Universe and caveats

- Universe: degree-granting institutions (`DEGGRANT == 1`) reporting 2024 undergraduate FTE.
- Blank cells mean "not reported", never zero. IPEDS suppresses or omits metrics
  that do not apply: open-admission colleges report no admit rate, and
  graduation rates require a qualifying cohort. Coverage is uneven:
  student-to-faculty ratio 3,646 of 3,649; graduation rate 3,377; admit rate
  1,810; retention 3,226; in-state tuition 3,339; Pell share 3,640.
- Small cohorts: graduation and retention rates from cohorts under 30 students
  (`gradCohort`, `retCohort`) are shown but not compared. That leaves 3,042
  graduation rates and 2,703 retention rates in medians, charts, the map and
  benchmarks. Before this rule, 123 institutions showed 100% retention, many
  from cohorts of one to eight students.
- Graduation rates measure completion within 150% of normal time: six years
  at four-year institutions, three at two-year institutions. Compare within
  level. The median is 53% for four-year and 42% for two-year institutions.
- Medians are computed over reporting institutions only.
- The forecast line is an ordinary least-squares fit on aggregate FTE for the
  current filter, extended three years. It is a descriptive trend, not a causal
  or institution-level projection.

## Sources

- [CDHE FTE Student Enrollment Reports](https://spl.cde.state.co.us/artemis/hedserials/)
- [JBC Higher Education briefings](https://content.leg.colorado.gov/sites/default/files/fy2026-27_hedbrf.pdf) and [FY2026-27 Long Bill narrative](https://content.leg.colorado.gov/sites/default/files/26LBNarrativeA.pdf)
- [CDHE funding formula](https://cdhe.colorado.gov/colorado-higher-education-funding-formula) and [HB26-1345](https://leg.colorado.gov/bills/hb26-1345)
- [BLS Denver CPI](https://www.bls.gov/regions/mountain-plains/co_denver_msa.htm)

- [NCES IPEDS](https://nces.ed.gov/ipeds/) and [survey components](https://nces.ed.gov/ipeds/survey-components)
- [NCES IPEDS Complete Data Files](https://nces.ed.gov/ipeds/use-the-data)
- [Urban Institute Education Data Portal](https://educationdata.urban.org/documentation/colleges.html) (reconciliation source)
- [Carnegie Classification](https://carnegieclassifications.acenet.edu/)
