# Contributing

Thanks for improving the companion code for *Data Science for Postsecondary
Education Metrics*. This repo favors small, well-tested, pure functions over
notebook-only logic, so every chapter notebook stays a thin assembly of
already-verified code.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Before opening a pull request

```bash
ruff check .          # lint
black --check .       # formatting
pytest --cov=src      # tests + coverage
```

All three run in CI (`.github/workflows/ci.yml`) against Python 3.10–3.12;
please make sure they pass locally first.

## Guidelines

- **New ingestion modules** (`src/ingest/`): confirm raw IPEDS variable names
  against the current year's [IPEDS data dictionary](https://nces.ed.gov/ipeds/use-the-data)
  before adding a rename mapping — NCES occasionally renames variables
  between release years.
- **New features** (`src/features/`): keep functions pure (DataFrame(s) in,
  DataFrame out, no I/O) so they stay unit-testable with small synthetic
  fixtures.
- **New models** (`src/models/`): add a documented baseline before a more
  complex model, and respect the panel's temporal structure (train on
  earlier years, test on later years) rather than a random split.
- **Validation** (`src/validation/`): any new benchmark check must cite the
  published source it compares against (a URL in the docstring or code
  comment) — never hardcode a benchmark value without a citation.
- **Tests**: add or update a fixture-based unit test for every new function.
  Fixtures live in `tests/fixtures/` and should stay small and synthetic —
  never commit real, restricted, or bulk IPEDS extracts.
- **Disclosure safety**: if your change surfaces subgroup-level counts,
  run it through `src.validation.disclosure_checks` before merging.

## Reporting data-correctness issues

If a computed metric disagrees with an institution's own published
[IPEDS Data Feedback Report](https://nces.ed.gov/ipeds/) or the
[Digest of Education Statistics](https://nces.ed.gov/programs/digest/), please
open an issue with both figures and their sources — see the bug report
template.
