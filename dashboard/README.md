# IPEDS Explorer — interactive dashboard

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
| `data/institutions.json` | 3,689 degree-granting institutions, 2023 primary year    |
| `data/us-states.json`    | Pre-projected Albers USA state outlines as SVG paths     |

## Rebuilding the data

Both files are generated, not hand-edited. From the repository root:

```bash
python -m src.ingest.build_dashboard_data_nces --year 2023   # -> dashboard/data/institutions.json
python -m src.ingest.build_us_map                            # -> dashboard/data/us-states.json
```

`build_dashboard_data_nces.py` reads the [NCES IPEDS Complete Data
Files](https://nces.ed.gov/ipeds/use-the-data) directly and caches the ZIPs in
`data/raw/nces/`. It prefers NCES's revised (`_rv`) releases and uses only final
data. The original `build_dashboard_data.py` reads the same collections through
the Urban Institute Education Data Portal and is kept as an independent check.

### Current vintage

| Metric group                                   | Year | NCES file             |
| ---------------------------------------------- | ---- | --------------------- |
| Directory, Carnegie 2021 basic classification  | 2023 | `HD2023`              |
| Student-to-faculty ratio, fall retention       | 2023 | `EF2023D`             |
| Admissions and yield                           | 2023 | `ADM2023`             |
| In-state and out-of-state tuition and fees     | 2023 | `IC2023_AY`           |
| In-district tuition and fees (`TUITION1+FEE1`) | 2023 | `IC2023_AY`           |
| Undergraduate 12-month FTE, 2013–2023 series   | 2023 | `EFIA2014`–`EFIA2024` |
| Graduation rate within 150% of normal time     | 2022 | `GR2023`              |
| Pell share and average Pell award              | 2022 | `SFA2223`             |

Years follow the start-of-academic-year convention used throughout the book,
so the 12-month enrollment file `EFIA2024` (2023–24) is labeled 2023. `GR2024`
and `SFA2324` belong to the 2024–25 collection, which NCES has released only as
provisional data, so graduation rates and aid stay one year behind.

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

- Universe: degree-granting institutions (`DEGGRANT == 1`) reporting 2023 undergraduate FTE.
- Blank cells mean "not reported", never zero. IPEDS suppresses or omits metrics
  that do not apply: open-admission colleges report no admit rate, and
  graduation rates require a qualifying cohort. Coverage is uneven:
  student-to-faculty ratio 3,682 of 3,689; graduation rate 3,398; admit rate
  1,821; retention 3,259; in-state tuition 3,373; Pell share 3,668.
- Graduation rates measure completion within 150% of normal time: six years
  at four-year institutions, three at two-year institutions. Compare within
  level. The median is 53% for four-year and 40% for two-year institutions.
- Medians are computed over reporting institutions only.
- The forecast line is an ordinary least-squares fit on aggregate FTE for the
  current filter, extended three years. It is a descriptive trend, not a causal
  or institution-level projection.

## Sources

- [NCES IPEDS](https://nces.ed.gov/ipeds/) and [survey components](https://nces.ed.gov/ipeds/survey-components)
- [NCES IPEDS Complete Data Files](https://nces.ed.gov/ipeds/use-the-data)
- [Urban Institute Education Data Portal](https://educationdata.urban.org/documentation/colleges.html) (reconciliation source)
- [Carnegie Classification](https://carnegieclassifications.acenet.edu/)
