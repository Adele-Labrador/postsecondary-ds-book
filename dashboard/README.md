# IPEDS Explorer — interactive dashboard

A static, dependency-light dashboard built on the same IPEDS panel the book's
modules produce. It is the visual companion to `src/` : the peer-group logic
mirrors `src/features/peer_groups.py`, and the FTE forecast mirrors the
descriptive-trend baseline in `src/models/forecast_enrollment.py`.

## Contents

| Path                        | Purpose                                                      |
| --------------------------- | ------------------------------------------------------------ |
| `index.html`                | Markup and CDN dependencies (Chart.js, d3-array, d3-geo)      |
| `styles.css`                | Design tokens, light/dark themes, layout                      |
| `app.js`                    | Data load, filtering, charts, map, table, detail drawer       |
| `data/institutions.json`    | 3,716 degree-granting institutions, 2022 primary year         |
| `data/us-states.json`       | Pre-projected Albers USA state outlines as SVG paths          |

## Rebuilding the data

Both files are generated, not hand-edited. From the repository root:

```bash
python -m src.ingest.build_dashboard_data   # -> dashboard/data/institutions.json
python -m src.ingest.build_us_map           # -> dashboard/data/us-states.json
```

`build_dashboard_data.py` pulls live IPEDS collections from the Urban Institute
Education Data Portal: directory and Carnegie classification, 12-month
undergraduate FTE (2013–2022), student-to-faculty ratio, admissions, 150%
graduation rates, fall retention, academic-year tuition, and student financial
aid. Financial-aid figures lag one year, so Pell metrics are 2021.

## Running locally

No build step. Serve the directory over HTTP (the JSON fetches need it):

```bash
cd dashboard && python3 -m http.server 8000
```

## Universe and caveats

- Universe: `degree_granting == 1` institutions reporting 2022 undergraduate FTE.
- Blank cells mean "not reported", never zero. IPEDS suppresses or omits metrics
  that do not apply — open-admission colleges report no admit rate, and
  graduation rates require a qualifying cohort. Coverage is therefore uneven:
  student-to-faculty ratio 3,707 of 3,716; graduation rate 2,224; admit rate
  1,826; retention 3,305; in-state tuition 3,395; Pell share 3,690.
- Medians are computed over reporting institutions only.
- The forecast line is an ordinary least-squares fit on aggregate FTE for the
  current filter, extended three years. It is a descriptive trend, not a causal
  or institution-level projection.

## Sources

- [NCES IPEDS](https://nces.ed.gov/ipeds/) and [survey components](https://nces.ed.gov/ipeds/survey-components)
- [Urban Institute Education Data Portal](https://educationdata.urban.org/documentation/colleges.html)
- [Carnegie Classification](https://carnegieclassifications.acenet.edu/)
