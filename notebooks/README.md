# Chapter notebooks

One notebook per book chapter, following the standard four-section contract
described in the curriculum map:

1. **Load** — read one slice of `data/processed/panel.parquet`.
2. **Target & split** — define the label/target and a temporal train/test
   split (train on years ≤ *t*, test on years > *t*) so evaluation respects
   the panel's time structure.
3. **Model** — fit a documented baseline before any more complex model.
4. **Validate** — run the matching function from `src/validation/` and
   report both statistical fit (RMSE/AUC/accuracy) and a comparison to a
   published benchmark.

Notebooks import only from `src/` — no analysis logic should live inside a
notebook cell that isn't reusable, testable code.

Suggested notebook-to-module mapping:

| Notebook | Uses |
|---|---|
| `03_building_the_panel.ipynb` | `src.ingest.*`, `src.features.panel_builder` |
| `04_peer_groups_and_carnegie.ipynb` | `src.features.peer_groups` |
| `05_forecasting_enrollment.ipynb` | `src.models.forecast_enrollment` |
| `07_student_faculty_ratio.ipynb` | `src.features.ratios.student_faculty_ratio` |
| `08_institutional_finance.ipynb` | `src.features.ratios.financial_health_ratios` |
| `09_financial_aid_modeling.ipynb` | `src.features.ratios.aid_intensity_index` |
| `11_graduation_rates_and_equity.ipynb` | `src.models.forecast_graduation_rate` |
| `12_institution_segmentation.ipynb` | `src.models.cluster_segments` |
| `13_validating_against_research.ipynb` | `src.validation.benchmark_checks`, `src.validation.disclosure_checks` |

No notebook files are checked in yet — this repo ships the underlying,
tested `src/` modules first (Phases 1–2 of the project roadmap) so each
notebook is a thin, low-risk assembly of already-verified functions.
