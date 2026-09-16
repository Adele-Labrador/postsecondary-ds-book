# Data Science for Postsecondary Education — Companion Repository

[![CI](https://github.com/OWNER/postsecondary-ds-book/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/postsecondary-ds-book/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

> Replace `OWNER` in the badge URL above with your GitHub username/org once this repo is pushed.

Reproducible starter code for the book *Data Science for Postsecondary Education
Metrics*. This repo turns public [IPEDS](https://nces.ed.gov/ipeds/) survey
files into an institution-year feature store, then trains and validates a set
of predictive ML tasks (institution-type classification, enrollment/graduation
forecasting, institution segmentation) against published benchmarks such as
the [Carnegie Classification](https://carnegieclassifications.acenet.edu/) and
NCES's own reported figures.

See the book's curriculum map for the full chapter-by-chapter plan; this repo
implements Phase 1–2 (ingestion + feature store) plus starter versions of the
Phase 3 modeling chapters and the Phase 4 validation checks.

## Repository layout

```
postsecondary-ds-book/
├── .github/
│   ├── workflows/ci.yml       # lint, format check, and test matrix (Python 3.10-3.12)
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── data/
│   ├── raw/          # untouched NCES downloads, one folder per survey-year
│   ├── interim/       # per-component standardized tables
│   └── processed/    # final institution-year feature store (parquet)
├── src/
│   ├── ingest/        # pull + standardize raw IPEDS survey components
│   ├── features/      # ratios, peer groups, panel assembly
│   ├── models/        # one module per predictive ML task
│   └── validation/     # benchmark comparisons + disclosure-safety checks
├── tests/              # unit tests + small synthetic fixtures for every module
├── notebooks/          # one notebook per book chapter (imports only from src/)
├── pyproject.toml      # project metadata + ruff/black/pytest/coverage config
├── requirements.txt    # runtime dependencies
├── requirements-dev.txt # + pytest-cov, ruff, black
├── LICENSE             # MIT
├── CONTRIBUTING.md
└── CODE_OF_CONDUCT.md
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

or with conda:

```bash
conda env create -f environment.yml
conda activate postsecondary-ds-book
```

## Running the tests

```bash
pip install -r requirements-dev.txt
ruff check .           # lint
black --check .        # formatting
pytest --cov=src       # tests + coverage
```

All tests run against small synthetic fixtures in `tests/fixtures/` — no
network access or real IPEDS download is required to verify the code works.
The same three commands run in [GitHub Actions CI](.github/workflows/ci.yml)
on every push and pull request, across Python 3.10, 3.11, and 3.12.

## Rebuilding the data pipeline

```bash
make data
```

runs, in order: ingest each raw component → apply the `unitid` crosswalk →
build engineered features → assemble the processed panel table.

## A note on real IPEDS variable codes

The raw column names referenced in `src/ingest/` (e.g. `EFTOTLT`, `CONTROL`,
`GRTOTLT`) follow IPEDS's documented naming conventions, but NCES occasionally
renames or restructures variables between survey years. Before pointing this
pipeline at a new release year, confirm current variable names against that
year's [IPEDS data dictionary](https://nces.ed.gov/ipeds/datacenter/InstitutionByGroup.aspx)
and the [Complete Data Files](https://nces.ed.gov/ipeds/use-the-data) page.

## Data sources

- NCES IPEDS [Complete Data Files](https://nces.ed.gov/ipeds/use-the-data) (CSV, by survey and year)
- [Urban Institute Education Data Portal API](https://educationdata.urban.org/documentation/) (programmatic alternative)
- [Carnegie Classification of Institutions of Higher Education](https://carnegieclassifications.acenet.edu/)
- [NCES Statistical Standards](https://nces.ed.gov/pubs2003/2003601.pdf) (disclosure limitation, data-quality guidance)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, coding conventions, and how
to add a new ingestion module, feature, model, or validation check. This
project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## License

Code in this repository is released under the [MIT License](LICENSE). IPEDS
data itself is public-domain U.S. government data; see [NCES's data-use
terms](https://nces.ed.gov/ipeds/) for details.
