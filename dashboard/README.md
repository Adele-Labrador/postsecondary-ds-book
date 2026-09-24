# IPEDS Explorer — interactive dashboard

Live at <https://adele-labrador.github.io/postsecondary-ds-book/>, redeployed
by `.github/workflows/pages.yml` on every push that touches `dashboard/`.

A static, dependency-light dashboard built on the same IPEDS panel the book's
modules produce. It is the visual companion to `src/` : the peer-group logic
mirrors `src/features/peer_groups.py`, and the FTE forecast mirrors the
descriptive-trend baseline in `src/models/forecast_enrollment.py`.

## Contents

| Path                     | Purpose                                                  |
| ------------------------ | -------------------------------------------------------- |
| `index.html`             | Markup and CDN dependencies (Chart.js, d3-array, d3-geo) |
| `styles.css`             | Design tokens, light/dark themes, layout                 |
| `app.js`                 | Data load, filtering, charts, map, table, detail drawer  |
| `data/institutions.json` | 3,649 degree-granting institutions, 2024 primary year    |
| `data/us-states.json`    | Pre-projected Albers USA state outlines as SVG paths     |

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

- [NCES IPEDS](https://nces.ed.gov/ipeds/) and [survey components](https://nces.ed.gov/ipeds/survey-components)
- [NCES IPEDS Complete Data Files](https://nces.ed.gov/ipeds/use-the-data)
- [Urban Institute Education Data Portal](https://educationdata.urban.org/documentation/colleges.html) (reconciliation source)
- [Carnegie Classification](https://carnegieclassifications.acenet.edu/)
