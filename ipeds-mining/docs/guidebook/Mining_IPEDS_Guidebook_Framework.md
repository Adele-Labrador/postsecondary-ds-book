# Mining IPEDS: A Practical Python Guide for the Analysis of Postsecondary Education Data

### A Technical Guidebook Framework in the Pedagogy of Statistics, Data Mining, and Machine Learning in Astronomy

**Working subtitle:** A Practical Python Guide for the Analysis of Institutional Survey Data

---

## Preface: Pedagogical Rationale

[Statistics, Data Mining, and Machine Learning in Astronomy (Ivezić, Connolly, VanderPlas & Gray, Princeton University Press)](https://press.princeton.edu/books/hardcover/9780691198309/statistics-data-mining-and-machine-learning-in-astronomy-pdf) is organized as a four-part progression — Introduction, Statistical Frameworks and Exploratory Data Analysis, Data Mining and Machine Learning, and Appendices — moving a reader from raw survey data and computational infrastructure, through classical and Bayesian inference, into structure-finding, dimensionality reduction, regression, classification, and time-series methods, each anchored to a real astronomical survey dataset and a reproducible Python notebook ([AstroML table of contents](https://www.astroml.org/_downloads/13c92f3e9771808544a36fb195fdc487/DMbookTOC.pdf); [dokumen.pub TOC](https://dokumen.pub/statistics-data-mining-and-machine-learning-in-astronomy-a-practical-python-guide-for-the-analysis-of-survey-data-course-booknbsped-9781400848911.html)).

This guidebook adopts that same five-part skeleton — **Introduction → Data Governance & EDA → Data Mining & Machine Learning → Applied Benchmarking Capstones → Appendices** — and re-grounds every chapter in the [Integrated Postsecondary Education Data System (IPEDS)](https://nces.ed.gov/ipeds/), the U.S. Department of Education's mandatory annual census of every institution that participates in federal Title IV student aid programs. Where the astronomy text pairs a statistical concept with a Sloan Digital Sky Survey (SDSS) catalog, this guidebook pairs it with one or more of the [12 interrelated IPEDS survey components](https://nces.ed.gov/ipeds/survey-components) — Institutional Characteristics (IC), Admissions (ADM), 12-Month Enrollment (E12), Fall Enrollment (EF), Completions (C), Graduation Rates (GR/GR200), Outcome Measures (OM), Student Financial Aid (SFA), Finance (F), and Human Resources (HR), plus Academic Libraries (AL) — each keyed to a common institutional identifier, **UNITID** ([IPEDS Data Collection System overview](https://www.csn.edu/sites/default/files/pdf_file/0034/158893/IPEDS-Data-Collection-System.pdf)).

Each chapter therefore has four fixed anchors, mirroring the astronomy text's pattern of "concept → dataset → worked code → exercises":

1. **A statistical or ML concept**, taught from first principles.
2. **A named IPEDS survey component (or merge of components)** as the worked dataset.
3. **A reproducible Jupyter notebook** implementing the method end-to-end in Python.
4. **A prediction or clustering exercise** the reader completes and benchmarks against a held-out answer notebook.

---

## Part I — Introduction

### Chapter 1. About This Guidebook and Supporting Material
Mirrors AstroML Ch. 1 ("About the Book and Supporting Material").

- What "data mining," "machine learning," and "institutional research" mean in the higher-education-analytics context, and how they differ from IPEDS's native reporting/compliance function.
- Repository layout: `/data/raw`, `/data/interim`, `/data/processed`, `/notebooks`, `/src`, `/exercises`, `/solutions`.
- Software stack: `pandas`, `numpy`, `scikit-learn`, `statsmodels`, `scipy.stats`, `matplotlib`/`seaborn`, `pymc` (Bayesian chapters), `jupyter`/`nbgrader` (for graded exercises).
- Conventions used in every notebook: a fixed random seed, a standard train/validation/test split policy, and a "data provenance" header cell that records source file, IPEDS survey year, and download date.

### Chapter 2. Acquiring and Engineering IPEDS at Scale
Mirrors AstroML Ch. 2 ("Fast Computation on Massive Data Sets").

- Programmatic acquisition via the [IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/IPEDSManual.pdf) bulk CSV/Access downloads versus the Use-the-Data Trend Generator and Complete Data Files; scripted retrieval with `requests`/`pandas.read_csv` and checksum verification.
- Table of the 12 survey components, their collection season (fall/winter/spring), and update cadence ([IPEDS survey components and data cycle](https://nces.ed.gov/ipeds/report-your-data/overview-survey-components-data-cycle)):

| Season | Components |
|---|---|
| Fall | Institutional Characteristics (IC), Completions (C), 12-Month Enrollment (E12) |
| Winter | Admissions (ADM), Graduation Rates (GR), 200% Graduation Rates (GR200), Outcome Measures (OM), Student Financial Aid (SFA) |
| Spring | Fall Enrollment (EF), Finance (F), Human Resources (HR), Academic Libraries (AL) |

- Building a multi-year longitudinal panel: `UNITID`-keyed merges across survey years, handling institutions that open, close, merge, or change UNITID; reconciling dictionary/variable-name drift between IPEDS "revision" cycles.
- Performance patterns for large joins: chunked reads, categorical dtypes, and an optional DuckDB/SQLite backend for multi-gigabyte multi-year panels — the IPEDS analogue of AstroML's "fast computation on massive data sets."

---

## Part II — Data Governance, Cleaning, and Exploratory Analysis
Mirrors AstroML Part II, "Statistical Frameworks and Exploratory Data Analysis" (Chs. 3–5).

### Chapter 3. The IPEDS Data Model, Cleaning, and De-Identification Workflow

This chapter defines the reproducible pipeline used by every later notebook. It is written as a linear workflow with explicit, testable steps:

**Step 1 — Ingest and schema-lock.** Load raw component CSVs with an explicit dtype map; freeze column names against the year's data dictionary to catch silent renames.

**Step 2 — Resolve reporter status and imputation.** Every numeric IPEDS cell carries a companion imputation flag indicating whether the value was reported, imputed, or not applicable ([IPEDS Data Collection System glossary](https://www.csn.edu/sites/default/files/pdf_file/0034/158893/IPEDS-Data-Collection-System.pdf); [Overview of IPEDS Data](https://nces.ed.gov/ipeds/use-the-data/overview-of-ipeds-data)). The workflow requires:
   - Retaining the imputation-flag columns rather than discarding them, and joining them to their target variable.
   - Coding a `data_quality` tier per observation (reported / imputed-from-prior-year / imputed-by-model / suppressed) so downstream models can weight or exclude low-quality cells.
   - Flagging "branch" or "child" campuses that report jointly with a parent UNITID, using the parent/child linkage variable, to avoid double-counting in aggregate statistics.

**Step 3 — Apply small-cell suppression and privacy screening for public redistribution.** Although IPEDS is institution-level (not student-level) public data, the guidebook enforces a de-identification discipline appropriate for a teaching corpus that will itself be redistributed, because (a) some components (HR, AL) contain free-text or contact fields not needed for analysis, and (b) small-n institutional cells can become identifying when finely cross-tabulated:
   - Drop or hash any free-text/contact columns (survey respondent name, email, phone) present in raw HR/IC extracts before the file leaves the raw layer.
   - Apply a minimum-cell-size rule (institutions with fewer than a threshold count of degree-seeking students, e.g. n < 15, per Chapter 3's suppression convention) and mask fine-grained race/ethnicity × gender × program cross-tabs below that threshold, following the precedent set by NCES's own suppression practice on demographic subgroup tables ([1998 IPEDS Academic Library Survey File confidentiality notes](https://nces.ed.gov/pubs2002/2002320.PDF)).
   - Generate a **synthetic institution ID crosswalk** (`SYN_ID ↔ UNITID`) stored only in a restricted lookup file outside the public exercise bundle, so that classroom benchmarking exercises can be distributed and auto-graded without letting students trivially "look up the answer" for a named institution before completing the modeling exercise; the crosswalk is revealed only in the instructor solution key.
   - Round derived rates (graduation rate, retention rate) to a fixed number of significant digits to prevent residual re-identification through back-calculation of small numerators.

**Step 4 — Harmonize and version.** Standardize units (fiscal year alignment for Finance, headcount vs. FTE for Enrollment), tag every processed file with a semantic version and a data-dictionary hash, and store the transformation script (not just the output) so every processed table is regenerable from raw inputs — the same reproducibility bar the astronomy text sets for its AstroML companion package.

**Notebook:** `01_ingest_clean_deidentify.ipynb` — implements Steps 1–4 against a chosen survey year and writes a versioned, de-identified analytic table to `/data/processed`.

### Chapter 4. Probability and Statistical Distributions in Institutional Data
Mirrors AstroML Ch. 3 ("Probability and Statistical Distributions").

- Descriptive statistics (mean, median, robust scale estimators — median absolute deviation, interquartile range) applied to heavy-tailed IPEDS Finance variables (endowment per FTE, instructional expenditure per FTE) and to enrollment counts.
- Distribution fitting: log-normal and Pareto-like tails in institutional revenue and endowment; Poisson/negative-binomial behavior in small-institution completions counts.
- Missing-data mechanisms (MCAR / MAR / MNAR) framed against the real non-response and imputation patterns documented in the IPEDS methodology, connecting Chapter 3's imputation flags to formal missing-data theory.
- **Notebook:** `02_distributions_and_missingness.ipynb`; **exercise:** fit and compare parametric vs. kernel density estimates of tuition and endowment-per-FTE across institutional sectors.

### Chapter 5. Classical Statistical Inference for Cross-Institutional Comparison
Mirrors AstroML Ch. 4 ("Classical Statistical Inference").

- Point estimation, confidence intervals, and hypothesis tests (two-sample t-test, Welch's test, one-way ANOVA, Kruskal–Wallis) for comparing sectors (public/private-nonprofit/private-for-profit), Carnegie classifications, or state systems on metrics such as six-year graduation rate or net price.
- Multiple-comparison correction (Bonferroni, Benjamini–Hochberg FDR) required whenever many institutions or many peer groups are compared simultaneously.
- Effect-size reporting (Cohen's d, eta-squared) alongside significance, to avoid over-interpreting differences driven by IPEDS's very large institution counts.
- **Notebook:** `03_classical_inference.ipynb`; **exercise:** test whether four-year public and four-year private nonprofit institutions differ significantly in first-to-second-year retention, with correction for multiple state-level subgroup tests.

### Chapter 6. Bayesian Statistical Inference for Small-n Institutions
Mirrors AstroML Ch. 5 ("Bayesian Statistical Inference").

- Why naïve rate estimates (e.g., graduation rate) are unstable for small colleges, and how hierarchical/multilevel Bayesian models with partial pooling shrink noisy small-institution estimates toward a sector- or state-level prior.
- Empirical Bayes and full Bayesian (MCMC, e.g., `pymc`) implementations of a beta-binomial model for graduation and retention rates.
- **Notebook:** `04_bayesian_shrinkage.ipynb`; **exercise:** build partially-pooled graduation-rate estimates for institutions with fewer than 200 first-time, full-time students and compare to raw GR-file rates.

---

## Part III — Data Mining and Machine Learning on IPEDS
Mirrors AstroML Part III, "Data Mining and Machine Learning" (Chs. 6–10), extended with a longitudinal chapter.

### Chapter 7. Searching for Structure — Clustering Institutions
Mirrors AstroML Ch. 6 ("Searching for Structure in Point Data").

- Non-parametric density estimation (KDE) over institutional feature space (size, selectivity, cost, staffing ratio).
- Clustering algorithms — k-means, hierarchical/agglomerative, Gaussian mixture models, DBSCAN — applied to a merged IC + EF + F + HR feature table to build data-driven **institutional peer groups**, contrasted against the externally defined Carnegie Classification.
- Cluster validation: silhouette score, gap statistic, and stability under bootstrap resampling.
- **Dataset:** IC + EF + F + HR merge, de-identified per Chapter 3. **Notebook:** `05_clustering_peer_groups.ipynb`. **ML exercise (clustering):** derive an unsupervised peer-group assignment for every four-year institution and compare cluster membership to Carnegie classification and to self-reported peer groups.

### Chapter 8. Dimensionality Reduction for Institutional Profiles
Mirrors AstroML Ch. 7 ("Dimensionality and Its Reduction").

- PCA on standardized IPEDS feature blocks (enrollment mix, finance ratios, staffing ratios, price/aid variables) to construct a low-dimensional "institutional landscape."
- Manifold methods (t-SNE, UMAP) for visualization; interpreting principal components as composite institutional-type axes (research intensity, access orientation, cost structure).
- **Notebook:** `06_pca_institutional_landscape.ipynb`; **exercise:** project all Title-IV institutions onto their first two principal components and identify outlier institutions.

### Chapter 9. Regression and Model Fitting — Predicting Financial and Enrollment Outcomes
Mirrors AstroML Ch. 8 ("Regression and Model Fitting").

- OLS, robust regression, and regularized regression (Ridge, Lasso, Elastic Net) predicting continuous IPEDS targets: net tuition revenue per FTE, total enrollment, instructional expenditure per FTE.
- Model-fitting fundamentals: train/validation/test partitioning by institution (not by row, to avoid leakage across years of the same UNITID), k-fold and leave-one-institution-out cross-validation, regularization-path selection.
- **ML exercise (prediction):** predict next-year Fall Enrollment (EF) from lagged enrollment, admissions yield, and price/aid variables; report RMSE and compare linear vs. regularized models. **Notebook:** `07_regression_enrollment_finance.ipynb`.

### Chapter 10. Classification — Predicting Completion and Risk Outcomes
Mirrors AstroML Ch. 9 ("Classification").

- Logistic regression, decision trees, random forests, gradient boosting, and support vector machines applied to a binary/ordinal target derived from Graduation Rates (GR/GR200) or Outcome Measures (OM) — e.g., "above/below sector-median six-year completion rate."
- Class imbalance handling, calibration, ROC/precision-recall evaluation, and feature-importance interpretation (permutation importance, SHAP) tying model output back to actionable institutional levers (financial aid intensity, student-faculty ratio, admissions selectivity).
- **ML exercise (prediction/classification):** build a completion-risk classifier from IC + ADM + SFA + HR features and evaluate it on a held-out year to test temporal generalization. **Notebook:** `08_classification_completion_risk.ipynb`.

### Chapter 11. Time Series and Longitudinal Analysis — Trends in Enrollment, Finance, and Completions
Mirrors and extends AstroML Ch. 10 ("Time Series Analysis") for panel/longitudinal institutional data.

- Constructing an institution × year panel from repeated IPEDS collections; panel-data models (pooled OLS, fixed-effects, random-effects) and the Hausman test for choosing between them.
- Mixed-effects growth-curve models for tracking within-institution trajectories (e.g., enrollment or graduation-rate trends) nested within state or sector.
- Classical time-series tools (ARIMA/SARIMA, exponential smoothing) for institution-level or sector-level enrollment forecasting; structural-break detection (Chow test, CUSUM) for identifying shocks such as the 2020 pandemic-era enrollment disruption.
- **Notebook:** `09_longitudinal_panel_models.ipynb`; **exercise:** fit fixed-effects models of graduation-rate trends by sector and forecast three-year-ahead enrollment for a chosen peer group.

---

## Part IV — Applied Capstones and Institutional Benchmarking

### Chapter 12. A Statistical Framework for Institutional Benchmarking

- Constructing defensible peer groups: combine Chapter 7's data-driven clusters with policy-defined peer lists; document selection criteria.
- Benchmarking statistics: percentile ranks, z-score scorecards, and weighted composite indices across enrollment, finance, and outcome metrics; explicit treatment of the multiple-comparison and small-n issues from Chapters 5–6 when ranking many institutions.
- Communicating uncertainty in benchmarking: confidence bands on ranks, and Bayesian credible intervals (Chapter 6) for small-institution comparisons, so single-year rank swings are not over-interpreted.
- **Notebook:** `10_benchmarking_scorecards.ipynb`.

### Chapter 13. Capstone Notebooks

Three fully worked, end-to-end capstones integrating prior chapters, each with a public "starter" notebook (data loading + EDA scaffold) and a private "solution" notebook:

1. **Enrollment Forecasting Capstone** — panel + time-series methods (Ch. 11) forecasting institutional and sector enrollment three years ahead.
2. **Completion & Peer-Clustering Capstone** — classification (Ch. 10) plus clustering (Ch. 7) to flag at-risk institutions within data-driven peer groups.
3. **Financial Health Early-Warning Capstone** — regression (Ch. 9) plus Bayesian shrinkage (Ch. 6) to build a composite financial-stress indicator for small-enrollment institutions.

---

## Notebook-to-IPEDS Variable Map

The cheat-sheet in Appendix D tells the reader which method each notebook teaches; this section tells the reader which raw IPEDS columns feed it. Variable names below are drawn from the native IPEDS Data Center column dictionaries and NCES's own program-generator label files wherever a code could be verified against an authoritative source (cited per row). Finance and Graduation Rates codes are pinned to the fiscal year 2023 / 2023–24 collection cycle in the year-anchored crosswalk immediately below, resolving the reporting-standard ambiguity that Chapter 3's Step 1 "schema-lock" is designed to handle for any other survey year. Every numeric column below has a companion imputation-flag column (native prefix `X`, e.g. `XRET_PCF`, `XSTUFACR`) that Chapter 3 requires each notebook to load alongside it ([NCES IPEDS program generator, EF2023D](https://nces.ed.gov/ipeds/program-generator?year=2023&tableName=EF2023D&type=spss)).

The four year-anchored crosswalks that follow document which columns exist and exactly what they mean. The operational counterpart — how each survey component is fetched, reshaped to its canonical grain, validated, and written to a curated table before any analysis notebook touches it — is specified in the companion volume, **Companion Jupyter Notebook Specifications**, which defines twelve component curation notebooks (`c01`–`c12`), the shared `ipeds_utils` module they depend on, and the contract mapping those twelve onto the ten analysis notebooks below.

All ten analysis notebooks named below are implemented with executable starter cells in the companion repository (`notebooks/01_*.ipynb` to `10_*.ipynb`), under the same file names and chapter pairings. Three mappings were refined by running them: finance totals use the part-level lines (`F1B27`/`F1C191`, `F2D16`/`F2E131`, `F3D09`/`F3E071`) because summary lines are blank for many parent/child filers; `RET_PCF` in the fall `t` release describes the fall `t − 1` cohort; and `DRVAL` library values attributed from a parent institution are blanked rather than treated as reported.

### Year-Anchored Finance and Graduation Rates Crosswalk (FY2023 / 2023–24 Collection Cycle)

This crosswalk pins every Finance and Graduation Rates variable used above to the exact native table and code for the most recently completed collection cycle — fiscal year 2023 Finance and the 2023 Graduation Rates cohort files — so Chapter 3's schema-lock step has a concrete target instead of a placeholder. Codes were confirmed directly against the official IPEDS Data Center data files and their accompanying variable dictionaries: GASB public institutions ([F2223_F1A data](https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A.zip), [F2223_F1A dictionary](https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A_Dict.zip)), FASB private-nonprofit and public-FASB institutions ([F2223_F2 data](https://nces.ed.gov/ipeds/datacenter/data/F2223_F2.zip), [F2223_F2 dictionary](https://nces.ed.gov/ipeds/datacenter/data/F2223_F2_Dict.zip)), FASB private for-profit institutions ([F2223_F3 data](https://nces.ed.gov/ipeds/datacenter/data/F2223_F3.zip), [F2223_F3 dictionary](https://nces.ed.gov/ipeds/datacenter/data/F2223_F3_Dict.zip)), the standard-harmonized derived-ratio file ([DRVF2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVF2023.zip), [DRVF2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVF2023_Dict.zip)), the raw cohort-level graduation-count file ([GR2023 data](https://nces.ed.gov/ipeds/datacenter/data/GR2023.zip), [GR2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/GR2023_Dict.zip)), the derived graduation/transfer-rate file ([DRVGR2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVGR2023.zip), [DRVGR2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVGR2023_Dict.zip)), and the 200%-of-normal-time bachelor's/less-than-4-year cohort mechanics file ([GR200_23 data](https://nces.ed.gov/ipeds/datacenter/data/GR200_23.zip), [GR200_23 dictionary](https://nces.ed.gov/ipeds/datacenter/data/GR200_23_Dict.zip)). Notebook 01's schema-lock step should route each `UNITID` to the correct Finance form by joining `CONTROL`/`SECTOR` from IC — public institutions report on F1A (GASB), private not-for-profit and a handful of FASB-reporting public institutions on F2, and private for-profit institutions on F3.

**Finance FY2023 — revenue line items, by reporting standard**

| Concept | GASB public (`F2223_F1A`) | FASB nonprofit / public-FASB (`F2223_F2`) | FASB for-profit (`F2223_F3`) |
|---|---|---|---|
| Tuition and fees | `F1B01` — "Tuition and fees, after deducting discounts and allowances" | `F2D01` — "Tuition and fees - Total" (memo allowance item `F2C08`) | `F3D01` — "Tuition and fees" (memo allowance item `F3C06`) |
| Federal appropriations | `F1B10` — "Federal appropriations" | `F2D02` — "Federal appropriations - Total" | `F3D02` — "Federal appropriations, grants and contracts" (combined) |
| State appropriations | `F1B11` — "State appropriations" | `F2D03` — "State appropriations - Total" | `F3D03` — "State and local appropriations, grants and contracts" (combined) |
| Local appropriations | `F1B12` — "Local appropriations, education district taxes, and similar support" | `F2D04` — "Local appropriations - Total" | (combined into `F3D03`) |
| Federal/state/local grants and contracts | `F1B02`/`F1B03`/`F1B04A` — "Federal/state/local operating grants and contracts" | `F2D05`/`F2D06`/`F2D07` — "Federal/state/local grants and contracts - Total" | (combined into `F3D02`/`F3D03`) |
| Private gifts, grants, and contracts | `F1B16` — "Gifts, including contributions from affiliated organizations" | `F2D08`/`F2D09` — "Private gifts, grants, and contracts - Total" / "Contributions from affiliated entities - Total" | `F3D04` — "Private gifts, grants, and contracts" |
| Investment income/return | `F1B17` — "Investment income" | `F2D10` — "Investment return - Total" | `F3D05` — "Investment income and investment gains (losses) included in net income" |
| Auxiliary enterprises revenue | `F1B05` — "Sales and services of auxiliary enterprises" | `F2D12` — "Sales and services of auxiliary enterprises - Total" | (not separately itemized on `F3D`) |
| Total revenues | `F1B27` — "Total operating and nonoperating revenues" | `F2D16` — "Total revenues and investment return - Total" | `F3D09` — "Total revenues and investment return" (Part D; not the identically titled `F3B01`, see note) |

**Finance FY2023 — expenses by function, by reporting standard**

| Concept | GASB public (`F2223_F1A`) | FASB nonprofit / public-FASB (`F2223_F2`) | FASB for-profit (`F2223_F3`) |
|---|---|---|---|
| Instruction | `F1C011` | `F2E011` | `F3E011` |
| Research | `F1C021` | `F2E021` | `F3E02A1` |
| Public service | `F1C031` | `F2E031` | `F3E02B1` |
| Academic support | `F1C051` | `F2E041` | `F3E03A1` |
| Student services | `F1C061` | `F2E051` | `F3E03B1` |
| Institutional support | `F1C071` | `F2E061` | `F3E03C1` |
| Scholarships/net grant aid to students | `F1C101` | `F2E081` | `F3E051` |
| Auxiliary enterprises | `F1C111` | `F2E071` | `F3E041` |
| Total expenses | `F1C191` | `F2E131` | `F3E071` |

Take totals from the revenue and expense detail parts (B/C for GASB, D/E for FASB), never from the FASB summary lines `F2B01`/`F3B01`. The finance forms instruct a parent institution to report Parts A and B for itself plus all of its child institutions ([IPEDS 2022-23 Finance form](https://nces.ed.gov/ipeds/use-the-data/download-survey-material/2022/finance/package_5_12.pdf)), so children leave those lines blank and parents report a system-wide figure. In FY2023 `F3B01` is blank for 1,592 of 2,090 for-profit filers, while `F3D09` is complete.

All nine rows carry the varTitle label "[Function] - Current year total" (GASB) or "[Function]-Total amount" (FASB), confirmed against the FY2023 data-file dictionaries linked above.

**Finance FY2023 — standard-harmonized derived ratios (`DRVF2023`)**

These are the variables Notebooks 05/06/07/09/10 should actually load for cross-sector benchmarking, since NCES has already normalized the accounting-standard differences above into one consistent naming scheme (`F1`=GASB, `F2`=FASB nonprofit, `F3`=FASB for-profit prefix, same suffix across all three):

| Concept | GASB (`F1…`) | FASB nonprofit (`F2…`) | FASB for-profit (`F3…`) |
|---|---|---|---|
| Core revenue, total $ | `F1CORREV` | `F2CORREV` | `F3CORREV` |
| Core expenses, total $ | `F1COREXP` | `F2COREXP` | `F3COREXP` |
| Tuition and fees, % of core revenue | `F1TUFEPC` | `F2TUFEPC` | `F3TUFEPC` |
| Tuition and fees revenue per FTE | `F1TUFEFT` | `F2TUFEFT` | `F3TUFEFT` |
| Government grants and contracts, % of core revenue | `F1GVGCPC` | `F2GVGCPC` | `F3GVGCPC` |
| Private gifts/grants/contracts, % of core revenue | `F1PGGCPC` | `F2PGGCPC` | `F3PGGCPC` |
| Investment return, % of core revenue | `F1INVRPC` | `F2INVRPC` | `F3INVRPC` |
| Instruction expense per FTE | `F1INSTFT` | `F2INSTFT` | `F3INSTFT` |
| Instruction expense, % of core expenses | `F1INSTPC` | `F2INSTPC` | `F3INSTPC` |
| Salaries and wages, % of total expenses | `F1SALRPC` | `F2SALRPC` | `F3SALRPC` |
| Equity/viability ratio | `F1EQUITR` | `F2EQUITR` | `F3EQUITR` |

GASB-only fields with no FASB analogue: `F1STAPPC`/`F1STAPFT` (state appropriations, % and per-FTE) and `F1LCAPPC`/`F1LCAPFT` (local appropriations, % and per-FTE), because appropriations are a public-sector-specific revenue stream. FASB-for-profit-only field: `F3SSEAPC`/`F3SSEAFT` (sales and services of educational activities), reflecting the for-profit form's different revenue taxonomy.

**Graduation Rates — raw cohort file (`GR2023`)**

`GR2023` is stored in long format: each row is one `UNITID` × `GRTYPE` (cohort data) × `CHRTSTAT` (graduation-rate status in cohort) × `SECTION` (survey-form section) × `COHORT` × `LINE` combination, with the headcount reported in `GRTOTLT`/`GRTOTLM`/`GRTOTLW` (grand total / men / women) and mirrored across nine race/ethnicity categories (`GRAIANT`, `GRASIAT`, `GRBKAAT`, `GRHISPT`, `GRNHPIT`, `GRWHITT`, `GR2MORT`, `GRUNKNT`, `GRNRALT`, each with a `T`/`M`/`W` suffix). Notebook 04's beta-binomial model should pivot on `CHRTSTAT` to separate the adjusted-cohort denominator rows from the completers-within-150%-of-time numerator rows before reshaping to wide format.

**Graduation Rates — derived rates (`DRVGR2023`)**

| Variable | Description |
|---|---|
| `GRRTTOT` | Graduation rate, total cohort (the all-programs completion rate used in Notebooks 04, 08, 09, 10) |
| `GRRTM`, `GRRTW` | Graduation rate, men / women |
| `GBA4RTT`, `GBA5RTT`, `GBA6RTT` | Bachelor's-degree graduation rate within 4 / 5 / 6 years, total cohort |
| `BAGR100`, `BAGR150`, `BAGR200` | Bachelor's-degree graduation rate within 100% / 150% / 200% of normal time (4-, 6-, and 8-year rates) |
| `L4GR100`, `L4GR150`, `L4GR200` | Degree/certificate graduation rate within 100% / 150% / 200% of normal time for less-than-4-year programs |
| `TRRTTOT`, `GBATRRT` | Transfer-out rate, total cohort / bachelor's cohort |
| `PGGRRTT`, `PGBA6RT` | Overall / 6-year bachelor's graduation rate for Pell Grant recipients |
| `SSGRRTT`, `SSBA6RT` | Overall / 6-year bachelor's graduation rate for Direct Subsidized Loan recipients not receiving Pell |
| `NRGRRTT`, `NRBA6RT` | Overall / 6-year bachelor's graduation rate for students receiving neither Pell nor subsidized loans |

**Graduation Rates — 150%/200%-of-time cohort mechanics (`GR200_23`)**

This file exposes the exact cohort-adjustment pipeline that Notebook 04's numerator/denominator pair and Notebook 08's classification target are built on, for both the bachelor's cohort (`BA*`, cohort year 2015) and the less-than-4-year cohort (`L4*`, cohort year 2019):

`BAREVCT` (revised cohort) → `BAEXCLU` (exclusions) → `BAAC150` (adjusted cohort, 150% of normal time) → `BANC100`/`BAGR100` (completers/rate at 100%) → `BANC150`/`BAGR150` (completers/rate at 150%) → `BAAEXCL` (additional exclusions) → `BAAC200` (adjusted cohort, 200% of normal time) → `BANC200`/`BAGR200` (completers/rate at 200%), with `BASTEND` ("still enrolled") accounting for students in the adjusted cohort who are neither completers nor exclusions. The `L4*` fields (`L4REVCT`, `L4EXCLU`, `L4AC150`, `L4NC100`/`L4GR100`, `L4NC150`/`L4GR150`, `L4AEXCL`, `L4AC200`, `L4NC200`/`L4GR200`, `L4STEND`) mirror this exact pipeline for less-than-4-year degree/certificate programs.

### Year-Anchored Enrollment, Admissions, and Financial Aid Crosswalk (Fall 2023 / 2022–23 Aid Year, 2023–24 Collection Cycle)

This crosswalk applies the same schema-lock discipline to three further survey components that feed Notebooks 02, 03, and 07–10: Admissions, Fall Enrollment, and Student Financial Aid. Codes were confirmed directly against the official IPEDS Data Center data files and dictionaries for the 2023–24 collection cycle: Admissions ([ADM2023 data](https://nces.ed.gov/ipeds/datacenter/data/ADM2023.zip), [ADM2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/ADM2023_Dict.zip)), derived admissions ratios ([DRVADM2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVADM2023.zip), [DRVADM2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVADM2023_Dict.zip)), Fall Enrollment by level/race/sex ([EF2023A data](https://nces.ed.gov/ipeds/datacenter/data/EF2023A.zip), [EF2023A dictionary](https://nces.ed.gov/ipeds/datacenter/data/EF2023A_Dict.zip)), Fall Enrollment retention and staffing ([EF2023D data](https://nces.ed.gov/ipeds/datacenter/data/EF2023D.zip), [EF2023D dictionary](https://nces.ed.gov/ipeds/datacenter/data/EF2023D_Dict.zip)), the standard-harmonized derived enrollment file ([DRVEF2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVEF2023.zip), [DRVEF2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVEF2023_Dict.zip)), and Student Financial Aid ([SFA2223 data](https://nces.ed.gov/ipeds/datacenter/data/SFA2223.zip), [SFA2223 dictionary](https://nces.ed.gov/ipeds/datacenter/data/SFA2223_Dict.zip)). Note the deliberate year offset baked into IPEDS itself: Fall 2023 Enrollment and Fall 2023 Admissions describe the cohort entering in fall 2023, while `SFA2223` reports aid actually disbursed for the 2022–23 aid year — both are collected together in the same spring 2024 collection window, so Notebook 01's schema-lock step must join on `UNITID` alone and treat the one-year aid lag as a documented feature of the panel, not a data-quality defect.

**Admissions, fall 2023 (`ADM2023`) — raw counts and test scores**

| Concept | Variable(s) | varTitle label |
|---|---|---|
| Applicants (total/men/women) | `APPLCN`/`APPLCNM`/`APPLCNW` | "Applicants total" / "Applicants men" / "Applicants women" |
| Admissions (total/men/women) | `ADMSSN`/`ADMSSNM`/`ADMSSNW` | "Admissions total" / "Admissions men" / "Admissions women" |
| Enrolled (total/men/women) | `ENRLT`/`ENRLM`/`ENRLW` | "Enrolled total" / "Enrolled men" / "Enrolled women" |
| Enrolled full-time / part-time | `ENRLFT`/`ENRLPT` | "Enrolled full time total" / "Enrolled part time total" |
| Test-score submission counts | `SATNUM`/`SATPCT`, `ACTNUM`/`ACTPCT` | "Number/Percent of first-time degree/certificate-seeking students submitting SAT/ACT scores" |
| SAT 25th/50th/75th percentile | `SATVR25`/`SATVR50`/`SATVR75` (EBRW), `SATMT25`/`SATMT50`/`SATMT75` (Math) | "SAT Evidence-Based Reading and Writing / Math [pctile] percentile score" |
| ACT 25th/50th/75th percentile | `ACTCM25`/`ACTCM50`/`ACTCM75` (Composite), `ACTEN25` (English), `ACTMT25` (Math) | "ACT Composite/English/Math [pctile] percentile score" |

**Derived admissions ratios (`DRVADM2023`)**

| Variable | varTitle label |
|---|---|
| `DVADM01`/`DVADM02`/`DVADM03` | Percent admitted — total / men / women |
| `DVADM04`/`DVADM05`/`DVADM06` | Admissions yield — total / men / women |
| `DVADM07`–`DVADM09` | Admissions yield — full time (total / men / women) |
| `DVADM10`–`DVADM12` | Admissions yield — part time (total / men / women) |

**Fall Enrollment, fall 2023, by level and race/ethnicity (`EF2023A`)**

`EF2023A` is long-format: each row is one `UNITID` × `EFALEVEL` (level of student) × `LINE` × `SECTION` (attendance status) × `LSTUDY` combination. Grand-total headcount is `EFTOTLT`/`EFTOTLM`/`EFTOTLW` ("Grand total" total/men/women), mirrored across nine race/ethnicity categories with a `T`/`M`/`W` suffix each: `EFAIANT` (American Indian or Alaska Native), `EFASIAT` (Asian), `EFBKAAT` (Black or African American), `EFHISPT` (Hispanic), `EFNHPIT` (Native Hawaiian or Other Pacific Islander), `EFWHITT` (White), `EF2MORT` (Two or more races), `EFUNKNT` (Race/ethnicity unknown), `EFNRALT` (U.S. Nonresident).

**Fall Enrollment retention and staffing, fall 2023 (`EF2023D`)**

| Concept | Variable(s) | varTitle label |
|---|---|---|
| GRS cohort size and entering class | `GRCOHRT`, `UGENTERN`, `PGRCOHRT` | "Full-time first-time degree/certificate-seeking undergraduate (current year GRS cohort)"; "Total entering students at the undergraduate level, fall 2023"; "Current year GRS cohort as a percent of entering class" |
| Full-time retention pipeline | `RRFTCT` → `RRFTEX`/`RRFTIN` → `RRFTCTA` → `RET_NMF`/`RET_PCF` | Full-time fall 2022 cohort → exclusions/inclusions → adjusted cohort → retained count/rate in fall 2023 |
| Part-time retention pipeline | `RRPTCT` → `RRPTEX`/`RRPTIN` → `RRPTCTA` → `RET_NMP`/`RET_PCP` | Part-time analogue of the full-time pipeline above |
| Staffing | `STUFACR` | "Student-to-faculty ratio" |

**Standard-harmonized derived enrollment ratios (`DRVEF2023`)**

| Concept | Variable(s) | varTitle label |
|---|---|---|
| Enrollment totals | `ENRTOT`, `FTE`, `ENRFT`, `ENRPT` | Total / full-time-equivalent / full-time / part-time enrollment |
| Race/sex composition | `PCTENRWH`, `PCTENRBK`, `PCTENRHS`, `PCTENRAS`, `PCTENRNH`, `PCTENRAN`, `PCTENR2M`, `PCTENRUN`, `PCTENRNR`, `PCTENRW` | "Percent of total enrollment that are [race/ethnicity]" / "...that are women" |
| Undergraduate/graduate mix | `EFUG`, `EFUG1ST`, `EFUGTRN`, `EFGRAD`, `PCTFT1ST` | Undergraduate / first-time / transfer-in / graduate enrollment; FTFT share of all undergraduates |
| Retention and staffing (mirrored from `EF2023D`) | `RET_PCF`, `RET_PCP`, `STUFACR` | Same labels as above, exposed on the harmonized file for direct joins in Notebooks 09–10 |
| Distance education mix | `PCTDEEXC`, `PCTDESOM`, `PCTDENON` | Percent of students enrolled exclusively / partially / not at all in distance education courses |

**Student Financial Aid, 2022–23 aid year (`SFA2223`)**

`SFA2223` reports two distinct cohorts that must not be conflated: the full-time, first-time (FTFT) degree/certificate-seeking cohort (unprefixed variable names) and the broader all-undergraduate cohort (`U`-prefixed variable names).

| Concept | FTFT cohort | All-undergraduate cohort |
|---|---|---|
| Cohort size | `SCUGRAD` ("Total number of undergraduates - financial aid cohort"), `SCUGFFN`/`SCUGFFP` (FTFT count/percent of all undergraduates) | — |
| Awarded any aid | `ANYAIDN`/`ANYAIDP` ("Number/Percent of full-time first-time undergraduates awarded any financial aid") | — |
| Any grant aid (federal/state/local/institutional) | `AGRNT_N`/`AGRNT_P`/`AGRNT_T`/`AGRNT_A` | `UAGRNTN`/`UAGRNTP`/`UAGRNTT`/`UAGRNTA` |
| Federal grant aid | `FGRNT_N`/`FGRNT_P`/`FGRNT_T`/`FGRNT_A` | — |
| Pell grant aid | `PGRNT_N`/`PGRNT_P`/`PGRNT_T`/`PGRNT_A` | `UPGRNTN`/`UPGRNTP`/`UPGRNTT`/`UPGRNTA` |
| State/local grant aid | `SGRNT_N`/`SGRNT_P`/`SGRNT_T`/`SGRNT_A` | — |
| Institutional grant aid | `IGRNT_N`/`IGRNT_P`/`IGRNT_T`/`IGRNT_A` | — |
| Student loans (any source) | `LOAN_N`/`LOAN_P`/`LOAN_T`/`LOAN_A` | — |
| Federal student loans | `FLOAN_N`/`FLOAN_P`/`FLOAN_T`/`FLOAN_A` | `UFLOANN`/`UFLOANP`/`UFLOANT`/`UFLOANA` |

Each `_N`/`N` suffix is a headcount, `_P`/`P` a percent of the relevant cohort, `_T`/`T` a total dollar amount, and `_A`/`A` an average dollar amount per recipient — confirmed against the `SFA2223` dictionary's varTitle column.

### Year-Anchored Completions and Outcome Measures Crosswalk (2022–23 Awards / 2015–16 Entering Cohort at 8 Years, 2023–24 Collection Cycle)

Codes were confirmed directly against the official IPEDS Data Center data files and dictionaries: completions by program, award level, and demographics ([C2023_A data](https://nces.ed.gov/ipeds/datacenter/data/C2023_A.zip), [C2023_A dictionary](https://nces.ed.gov/ipeds/datacenter/data/C2023_A_Dict.zip)), institution-level completions summary by race/sex ([C2023_B data](https://nces.ed.gov/ipeds/datacenter/data/C2023_B.zip), [C2023_B dictionary](https://nces.ed.gov/ipeds/datacenter/data/C2023_B_Dict.zip)), completions summary by age ([C2023_C data](https://nces.ed.gov/ipeds/datacenter/data/C2023_C.zip), [C2023_C dictionary](https://nces.ed.gov/ipeds/datacenter/data/C2023_C_Dict.zip)), derived completions by degree level ([DRVC2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVC2023.zip), [DRVC2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVC2023_Dict.zip)), the raw Outcome Measures cohort file ([OM2023 data](https://nces.ed.gov/ipeds/datacenter/data/OM2023.zip), [OM2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/OM2023_Dict.zip)), and the derived Outcome Measures percentages file ([DRVOM2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVOM2023.zip), [DRVOM2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVOM2023_Dict.zip)). Two more year-anchoring nuances for Notebook 01's schema-lock step: `C2023_A`/`C2023_B`/`C2023_C` report awards conferred between July 1, 2022 and June 30, 2023 — the same one-year-back pattern already documented for `SFA2223` — even though the files are named with the 2023 collection-cycle year; and `OM2023` tracks the cohort that entered in 2015–16, with the newest status point being the 8-year mark measured as of August 31, 2023, so "OM2023" always refers to the collection year of the 8-year outcome, not the entry year.

**Completions by program, award level, and demographics (`C2023_A`)**

`C2023_A` is long-format: each record is uniquely defined by `UNITID` × `CIPCODE` (2020 Classification of Instructional Programs) × `MAJORNUM` (first or second major) × `AWLEVEL` (award-level code). Grand-total awards are `CTOTALT`/`CTOTALM`/`CTOTALW`, mirrored across nine race/ethnicity categories with a `T`/`M`/`W` suffix each: `CAIANT` (American Indian or Alaska Native), `CASIAT` (Asian), `CBKAAT` (Black or African American), `CHISPT` (Hispanic or Latino), `CNHPIT` (Native Hawaiian or Other Pacific Islander), `CWHITT` (White), `C2MORT` (Two or more races), `CUNKNT` (Race/ethnicity unknown), `CNRALT` (U.S. Nonresident).

**Completions summary by age at award (`C2023_C`)**

| Variable | varTitle label |
|---|---|
| `AWLEVELC` | Award level code |
| `CSTOTLT`/`CSTOTLM`/`CSTOTLW` | Grand total / men / women awards, summed to the institution × award-level grain |
| `CSUND18`, `CS18_24`, `CS25_39`, `CSABV40` | Awards to completers ages under 18 / 18–24 / 25–39 / 40 and above |

**Derived completions by degree level, unique completers (`DRVC2023`)**

| Variable(s) | varTitle label |
|---|---|
| `ASCDEG`, `BASDEG`, `MASDEG` | Associate's / Bachelor's / Master's degrees awarded |
| `DOCDEGRS`, `DOCDEGPP`, `DOCDEGOT` | Doctor's degrees — research/scholarship / professional practice / other |
| `CERT1` (`CERT1A` \<12 weeks, `CERT1B` 12 weeks–1 year), `CERT2`, `CERT4` | Certificates of less than 1 year (with sub-splits) / 1–2 years / 2–4 years |
| `PBACERT`, `PMACERT` | Postbaccalaureate / post-master's certificates |
| `SASCDEG`, `SBASDEG`, `SMASDEG`, `SDOCDEG`, `SCERT1A`, `SCERT1B`, `SCERT24`, `SBAMACRT` | Number of unique students (not awards) receiving each credential type — the de-duplicated completer counts, distinct from the award counts above since one student can earn multiple awards |

**Outcome Measures raw cohort file, 2015–16 entering cohort (`OM2023`)**

`OM2023` is long-format with one row per `UNITID` × `OMCHRT` (cohort category: full-time/part-time × first-time/non-first-time × Pell/non-Pell, eight subcohorts total). Cohort-sizing fields are `OMRCHRT` ("2015-16 cohort") → `OMEXCLS` (exclusions) → `OMACHRT` (adjusted cohort). Outcomes are reported at three status points — 4 years (August 31, 2019), 6 years (August 31, 2021), and 8 years (August 31, 2023) — via `OMCERT4`/`OMASSC4`/`OMBACH4`/`OMAWDN4`/`OMAWDP4` (certificate/associate's/bachelor's/any-award count/any-award percent at 4 years), with `6` and `8` suffix analogues; the 8-year status point additionally reports subsequent-enrollment detail: `OMENRYI` (still enrolled at your institution), `OMENRAI` (enrolled at another institution), `OMENRUN` (enrollment status unknown), `OMNOAWD` (no award and not known to be enrolled), and their percent counterparts `OMENRTP`/`OMENRYP`/`OMENRAP`/`OMENRUP`.

**Derived Outcome Measures percentages by subcohort and Pell status (`DRVOM2023`)**

Variable names follow the pattern `OM{subcohort}{Pell status}{outcome}{status point}`, e.g. `OM1TOTLAWDP8` = subcohort 1, all students, award percent, 8 years:

| Position | Codes | Meaning |
|---|---|---|
| Subcohort (`OM1`–`OM4`) | `OM1`=full-time first-time, `OM2`=part-time first-time, `OM3`=full-time non-first-time, `OM4`=part-time non-first-time | Entry-status subcohort |
| Pell status | `TOTL`=all students, `PELL`=Pell recipients, `NPEL`=non-Pell recipients | Aid-status subgroup |
| Outcome | `AWDP`=any award %, `CRTP`/`ASCP`/`BACP`=certificate/associate's/bachelor's %, `ENYP`/`ENAP`/`ENUP`=still-enrolled-here/elsewhere/unknown % | Outcome type (8-year status point only for enrollment breakdowns) |
| Status point | `4`/`6`/`8` | Years since 2015–16 entry (August 31, 2019 / 2021 / 2023) |

Example confirmed labels: `OM1TOTLAWDP8` = "Percent full-time first-time receiving an award - 8 years"; `OM1PELLAWDP8` = "Percent full-time first-time, Pell grant recipients receiving an award - 8 years"; `OM1NPELAWDP8` = "Percent full-time first-time, non-Pell recipients receiving an award - 8 years."

### Year-Anchored Directory, Institutional Characteristics, 12-Month Enrollment, Human Resources, and Academic Libraries Crosswalk (2023–24 Collection Cycle)

This crosswalk closes out the remaining survey components. Codes were confirmed against the official files and dictionaries: the IPEDS Directory ([HD2023 data](https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip), [HD2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/HD2023_Dict.zip)), Institutional Characteristics ([IC2023 data](https://nces.ed.gov/ipeds/datacenter/data/IC2023.zip), [IC2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/IC2023_Dict.zip)), student charges for a full academic year ([IC2023_AY data](https://nces.ed.gov/ipeds/datacenter/data/IC2023_AY.zip), [IC2023_AY dictionary](https://nces.ed.gov/ipeds/datacenter/data/IC2023_AY_Dict.zip)), derived price trends ([DRVIC2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVIC2023.zip), [DRVIC2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVIC2023_Dict.zip)), 12-month unduplicated headcount ([EFFY2023 data](https://nces.ed.gov/ipeds/datacenter/data/EFFY2023.zip), [EFFY2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/EFFY2023_Dict.zip)), 12-month instructional activity ([EFIA2023 data](https://nces.ed.gov/ipeds/datacenter/data/EFIA2023.zip), [EFIA2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/EFIA2023_Dict.zip)), derived 12-month enrollment ([DRVEF122023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVEF122023.zip), [DRVEF122023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVEF122023_Dict.zip)), staff by occupational category ([S2023_OC data](https://nces.ed.gov/ipeds/datacenter/data/S2023_OC.zip), [S2023_OC dictionary](https://nces.ed.gov/ipeds/datacenter/data/S2023_OC_Dict.zip)), instructional staff by tenure status ([S2023_IS data](https://nces.ed.gov/ipeds/datacenter/data/S2023_IS.zip), [S2023_SIS data](https://nces.ed.gov/ipeds/datacenter/data/S2023_SIS.zip), [S2023_SIS dictionary](https://nces.ed.gov/ipeds/datacenter/data/S2023_SIS_Dict.zip)), new hires ([S2023_NH data](https://nces.ed.gov/ipeds/datacenter/data/S2023_NH.zip), [S2023_NH dictionary](https://nces.ed.gov/ipeds/datacenter/data/S2023_NH_Dict.zip)), instructional salaries ([SAL2023_IS data](https://nces.ed.gov/ipeds/datacenter/data/SAL2023_IS.zip), [SAL2023_IS dictionary](https://nces.ed.gov/ipeds/datacenter/data/SAL2023_IS_Dict.zip)), derived HR measures ([DRVHR2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVHR2023.zip), [DRVHR2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVHR2023_Dict.zip)), and Academic Libraries ([AL2023 data](https://nces.ed.gov/ipeds/datacenter/data/AL2023.zip), [DRVAL2023 data](https://nces.ed.gov/ipeds/datacenter/data/DRVAL2023.zip), [DRVAL2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVAL2023_Dict.zip)).

**Reference periods confirmed from each file's Introduction sheet** — these differ across components within the same collection cycle and must be recorded in Notebook 01's schema-lock step before any panel is assembled:

| File | Reference period as documented |
|---|---|
| `HD2023`, `IC2023` | 2023–24 IPEDS universe / collection year |
| `IC2023_AY`, `DRVIC2023` | Student charges for academic year 2023–24 |
| `EFFY2023`, `EFIA2023`, `DRVEF122023` | 12-month period July 1, 2022 – June 30, 2023 (the one-year-back pattern, as with `SFA2223` and `C2023_A`) |
| `S2023_OC`, `S2023_IS`, `S2023_SIS` | Staff on the payroll as of November 1, 2023 (Fall 2023) |
| `S2023_NH` | Full-time new hires between November 1, 2022 and October 31, 2023 |
| `SAL2023_IS`, `DRVHR2023` | Salary outlays for academic year 2023–24 |
| `AL2023`, `DRVAL2023` | Fiscal year 2023 |

**Directory, classification, and geography (`HD2023`)**

| Variable | varTitle label |
|---|---|
| `INSTNM`, `OPEID` | Institution (entity) name; Office of Postsecondary Education (OPE) ID Number — both dropped from the public de-identified layer |
| `CONTROL`, `SECTOR`, `ICLEVEL`, `HLOFFER` | Control of institution; sector of institution; level of institution; highest level of offering |
| `C21BASIC`, `C21ENPRF`, `C21SZSET` | Carnegie Classification 2021: Basic / Enrollment Profile / Size and Setting — the external typology against which Chapter 7's clusters are validated |
| `HBCU`, `TRIBAL`, `LANDGRNT`, `MEDICAL` | Historically Black College or University; Tribal college; Land Grant Institution; institution grants a medical degree — mission-type indicators that must be held constant in peer benchmarking |
| `LOCALE`, `CBSA`, `STABBR`, `FIPS`, `OBEREG` | Degree of urbanization (Urban-centric locale); Core Based Statistical Area; state abbreviation; FIPS state code; Bureau of Economic Analysis (BEA) regions |
| `INSTSIZE` | Institution size category |
| `CYACTIVE`, `PSEFLAG`, `POSTSEC`, `DEATHYR` | Institution is active in current year; postsecondary institution indicator; primarily postsecondary indicator; year institution was deleted from IPEDS — the universe filters that prevent closed institutions from contaminating a longitudinal panel |

**Institutional Characteristics and published price (`IC2023`, `IC2023_AY`, `DRVIC2023`)**

| Variable | varTitle label |
|---|---|
| `LEVEL1`, `LEVEL2`, `LEVEL3`, `LEVEL5` | Award-offering flags: certificate of less than 1 year; certificate of at least 1 but less than 2 years; associate's degree; bachelor's degree |
| `CALSYS`, `OPENADMP` | Calendar system; open admission policy |
| `DSTNCED1`, `DSTNCED2`, `DSTNCED3` | Undergraduate / graduate distance-education programs offered; does not offer distance education opportunities |
| `TUITION1`/`FEE1`, `TUITION2`/`FEE2`, `TUITION3`/`FEE3` | In-district / in-state / out-of-state average tuition and required fees for full-time undergraduates (`IC2023_AY`) |
| `TUITION5`–`TUITION7`, `FEE5`–`FEE7` | The same in-district / in-state / out-of-state split for full-time graduates |
| `CHG1AY3`, `CHG2AY3`, `CHG3AY3` | Published in-district / in-state / out-of-state tuition and fees, 2023–24 |
| `CHG4AY3`–`CHG9AY3` | Books and supplies; on-campus food and housing; on-campus other expenses; off-campus (not with family) food and housing and other expenses; off-campus (with family) other expenses — the cost-of-attendance components |
| `TUFEYR0`, `TUFEYR1`, `TUFEYR2`, `TUFEYR3` | Tuition and fees for 2020–21, 2021–22, 2022–23, and 2023–24 on a single row (`DRVIC2023`) — a pre-built four-year price series, which spares Notebook 09 a multi-vintage merge for this one measure |
| `CINSON`, `COTSON`, `CINSOFF`, `COTSOFF`, `CINSFAM`, `COTSFAM` | Total price for in-state / out-of-state students living on campus, off campus (not with family), and off campus (with family), 2023–24 |

**12-Month Enrollment and instructional activity (`EFFY2023`, `EFIA2023`, `DRVEF122023`)**

`EFFY2023` is long-format, keyed by `UNITID` × `EFFYALEV` ("Level and degree/certificate-seeking status of student"), with `EFFYLEV` and `LSTUDY` as coarser level indicators. Counts follow the same grand-total-plus-nine-race-categories pattern as Fall Enrollment but with an `EFY` prefix: `EFYTOTLT`/`EFYTOTLM`/`EFYTOTLW`, then `EFYAIANT`, `EFYASIAT`, `EFYBKAAT`, `EFYHISPT`, `EFYNHPIT`, `EFYWHITT`, `EFY2MORT`, `EFYUNKNT`, `EFYNRALT` (each with `M`/`W` variants), plus the gender-inclusive fields `EFYGUUN` (gender unknown), `EFYGUAN` (another gender), `EFYGUTOT`, and `EFYGUKN`.

| Variable | varTitle label |
|---|---|
| `CDACTUA`, `CNACTUA`, `CDACTGA` | 12-month instructional activity credit hours: undergraduates; clock hours: undergraduates; credit hours: graduates (`EFIA2023`) |
| `ACTTYPE` | Is instructional activity based on credit or clock hours — must be checked before comparing activity across institutions |
| `EFTEUG`, `EFTEGD` vs. `FTEUG`, `FTEGD`, `FTEDPP` | Estimated (NCES-derived) versus institution-reported full-time equivalent undergraduate, graduate, and doctors-professional-practice enrollment, 2022–23 — the reported/derived distinction is itself a data-quality exercise |
| `UNDUP`, `UNDUPUG`, `E12GRAD` | Total, undergraduate, and graduate 12-month unduplicated headcount (`DRVEF122023`) |
| `FTE12MN` | 12-month full-time equivalent enrollment |
| `E12FT`, `E12PT`, `E12UGFT`, `E12UGPT`, `E12GRADFT`, `E12GRADPT` | Full-time and part-time 12-month unduplicated headcount, overall and by undergraduate/graduate level |
| `E12UG1ST`, `E12UGTRN`, `E12UGCNT`, `E12UGNDG` | First-time, transfer-in, continuing, and nondegree/certificate-seeking undergraduate headcount (each also with `FT`/`PT` suffixes, e.g. `E12UG1SFT`, `E12UG1SPT`) |
| `PCTE12AN`…`PCTE12NR`, `PCTE12W` | Percent of 12-month unduplicated headcount by each race/ethnicity category and percent women (with `UG` and `GRAD` infixes for level-specific versions, e.g. `PCTE12UGBK`, `PCTE12GRADW`) |
| `PCTE12DEEXC`, `PCTE12DESOM`, `PCTE12DENON` | Percent enrolled exclusively in / in some but not all / in no distance-education courses (also `PCTE12UGDE*` and `PCTE12GRADDE*`) — the online-modality mix feature |

**Human Resources (`S2023_OC`, `S2023_SIS`, `S2023_NH`, `SAL2023_IS`, `DRVHR2023`)**

A correction to an earlier draft of this variable map is warranted here. The staffing-mix and tenure-density features in Notebooks 05/06 and 08 were originally sourced to the new-hires file via `SNHCAT`/`OCCUPCAT`/`FACSTAT`. Those variable names are real and do appear in `S2023_NH`, but that file counts only full-time employees hired between November 1, 2022 and October 31, 2023 — an annual hiring flow. A staffing-mix or tenure-density feature needs the standing stock of all staff, which lives in `S2023_OC` (keyed `UNITID` × `STAFFCAT`) and `S2023_SIS`/`S2023_IS` (keyed by `FACSTAT` and academic rank). The notebook rows below have been re-pointed accordingly; `S2023_NH` is retained only for genuine hiring-flow questions.

| Variable | varTitle label |
|---|---|
| `STAFFCAT`, `FTPT`, `OCCUPCAT`, `SABDTYPE` | Occupation and full-/part-time status (the `S2023_OC` record key); full-time or part-time status; occupation category; identifies occupations consistent with previous codes |
| `HRTOTLT`/`HRTOTLM`/`HRTOTLW` plus `HRAIANT`…`HRNRALT` | Grand total and nine race/ethnicity staff counts (each with `M`/`W` variants) — the same suffix grammar as enrollment and completions, shared by `S2023_OC` and `S2023_NH` |
| `FACSTAT` | Faculty and tenure status (the `S2023_SIS` key) |
| `SISTOTL`, `SISPROF`, `SISASCP`, `SISASTP`, `SISINST`, `SISLECT`, `SISNORK` | Full-time instructional staff at all ranks / professors / associate professors / assistant professors / instructors / lecturers / no academic rank, crossed with `FACSTAT` to give tenure density by rank |
| `SNHCAT` | Staff category (the `S2023_NH` new-hires key) — hiring flow only |
| `ARANK` | Academic rank (the `SAL2023_IS` key) |
| `SAINSTT`/`SAINSTM`/`SAINSTW`, `SAOUTLT`/`SAOUTLM`/`SAOUTLW` | Instructional staff counts and total salary outlays, by gender — the numerator/denominator pair for gender pay-gap analysis |
| `SAEQ9AT`/`SAEQ9AM`/`SAEQ9AW`, `SAEQ9OT` | Average salary and salary outlays for instructional staff equated to a 9-month contract, total/men/women — the contract-length-adjusted figures required for any cross-institution salary comparison |
| `SA09MAT`, `SA10MAT`, `SA11MAT`, `SA12MAT` | Average salary for instructional staff on 9-, 10-, 11-, and 12-month contracts (each with `M`/`W` gender variants) |
| `SALTOTL`, `SALPROF`, `SALASSC`, `SALASST`, `SALINST`, `SALLECT`, `SALNRNK` | Average 9-month-equated salary of full-time instructional staff by rank, pre-computed on `DRVHR2023` |
| `SFTETOTL`, `SFTEINST`, `SFTERSRC`, `SFTEPBSV`, `SFTEPSTC` | Total FTE staff; instructional FTE; research FTE; public service FTE; combined instructional/research/public-service FTE — the mission-allocation shares |
| `SFTEMNGM`, `SFTEBFO`, `SFTECES`, `SFTELCA`, `SFTEOTIS`, `SFTEHLTH`, `SFTEOFAS`, `SFTEOTHR` | Management; business and financial operations; computer, engineering, and science; librarians, curators, and archivists; student and academic affairs and other education services; healthcare; office and administrative support; and residual-category FTE — the administrative-intensity denominators |

**Academic Libraries (`AL2023`, `DRVAL2023`)**

| Variable | varTitle label |
|---|---|
| `LEXP100K`, `LCOLELYN`, `LILLDYN`, `LILSYN`, `LFRNGBYN` | Screener flags: were annual total library expenses at least $100,000; is the collection entirely electronic; are interlibrary loan services offered; does the institution have library staff; are fringe benefits paid from the library budget — each gates whether downstream fields are populated, making this file a natural structural-missingness case study |
| `LPBOOKS`, `LEBOOKS`, `LEDATAB`, `LPMEDIA`, `LEMEDIA`, `LPSERIA`, `LESERIA` | Physical and digital/electronic books, databases, media, and serials counts |
| `LPCLLCT`, `LECLLCT`, `LTCLLCT` | Total physical / electronic / combined library collections |
| `LPCRCLT`, `LECRCLT`, `LTCRCLT` | Total physical / digital-electronic / combined library circulations |
| `LILLDPR`, `LILLDRC` | Interlibrary loans and documents provided to other libraries; received |
| `LSTOTAL`, `LSLIBRN`, `LSOPROF`, `LSOPAID`, `LSSTAST`, `LBRANCH` | Total library FTE staff; librarians; other professional; all other paid (except student assistants); student assistants; number of branches and independent libraries |
| `LSALWAG`, `LFRNGBN`, `LEXMSTL` (`LEXMSBB`, `LEXMSCS`, `LEXMSOT`), `LEXOMTL` (`LEXOMPS`, `LEXOMOT`), `LEXPTOT` | Salaries and wages; fringe benefits; total materials/services expenditures split into one-time purchases, ongoing subscription commitments, and other; total operations and maintenance split into preservation and other; and total expenditures |
| `LPBOOKSP`, `LEBOOKSP`, `LEDATABP`, `LESERIAP` (and physical/electronic media and serial analogues) | Each collection type as a percent of the total collection (`DRVAL2023`) — the print-to-digital transition share used in Chapter 11's trend work |
| `LSALWAGP`, `LFRNGBNP`, `LEXMSCSP`, `LEXMSBBP`, `LEXOMTLP` | Salaries, fringe benefits, subscription commitments, one-time purchases, and operations/maintenance as percents of total library expenditures |
| `LEXPTOTF` | Total library expenditures per FTE — the size-normalized benchmarking measure |
| `LTOTLFTE`, `LLIBRFTE`, `LPROFFTE`, `LPAIDFTE`, `LSTUDFTE` | Library FTE staff totals by category, pre-computed |

### 01_ingest_clean_deidentify.ipynb — cross-cutting keys, flags, and directory fields

| Variable | Survey file | Description |
|---|---|---|
| `UNITID` | All components | Unique 6-digit institution identifier; the join key for every merge in the guidebook ([IPEDS Data Collection System](https://www.csn.edu/sites/default/files/pdf_file/0034/158893/IPEDS-Data-Collection-System.pdf)) |
| `INSTNM`, `OPEID` | Institutional Characteristics (IC) | Institution name and Office of Postsecondary Education ID; dropped from the public de-identified layer and retained only in the restricted crosswalk |
| `CONTROL`, `SECTOR`, `ICLEVEL`, `HLOFFER` | Directory / IC, 2023–24 (`HD2023`) | Public/private-nonprofit/private-for-profit control, 9-category sector, level (4-year+/2-year/less-than-2-year), and highest level of offering, used throughout as stratification variables, see crosswalk above ([HD2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/HD2023_Dict.zip)) |
| `CYACTIVE`, `PSEFLAG`, `DEATHYR` | `HD2023` | Universe filters applied before any panel is built, so that institutions that closed or left the IPEDS universe mid-series do not produce spurious trend breaks |
| `C21BASIC`, `C21ENPRF`, `C21SZSET` | `HD2023` | Carnegie Classification 2021 basic type, enrollment profile, and size/setting — the external validation labels for Chapters 7–8 |
| `STAT_OM`, `PRCH_OM`, `IDX_OM`, `PCOM_F` (and the analogous `STAT_`/`PRCH_`/`IDX_` flags on every other component) | OM and all components | Response status, parent/child branch-campus indicator, parent UNITID, and allocation factor, used to de-duplicate branch campuses before any aggregate statistic is computed ([NCES program generator, FLAGS2024](https://nces.ed.gov/ipeds/program-generator?year=2024&tableName=FLAGS2024&type=stata)) |
| `X`-prefixed imputation flags (e.g. `XEFTOTLT`, `XRET_PCF`) | All components | Per-cell imputation status (reported / imputed / not applicable), joined to every target variable and used to build the `data_quality` tier in Step 2 |

### 02_distributions_and_missingness.ipynb — Finance and Enrollment distributions

| Variable | Survey file | Description |
|---|---|---|
| `EFTOTLT`, `EFTOTLM`, `EFTOTLW`, `EFALEVEL` | Fall Enrollment (EF), fall 2023 (`EF2023A`) | Total/male/female fall headcount by student level, the base enrollment series, see crosswalk above ([EF2023A dictionary](https://nces.ed.gov/ipeds/datacenter/data/EF2023A_Dict.zip)) |
| `STUFACR` | EF, fall 2023 (`EF2023D`) | Student-to-faculty ratio, a right-skewed variable used to demonstrate robust scale estimators ([EF2023D dictionary](https://nces.ed.gov/ipeds/datacenter/data/EF2023D_Dict.zip)) |
| Tuition and fees (`F1B01` GASB / `F2D01` FASB nonprofit / `F3D01` FASB for-profit) and investment income (`F1B17` / `F2D10` / `F3D05`) — FY2023 codes, see crosswalk above | Finance (F) | Net tuition-and-fee revenue and investment return/endowment income, the heavy-tailed variables used for log-normal fitting ([F2223_F1A dictionary](https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A_Dict.zip); [F2223_F2 dictionary](https://nces.ed.gov/ipeds/datacenter/data/F2223_F2_Dict.zip)) |
| `CTOTALT` grouped by `UNITID` (award count per institution, summed across `CIPCODE`/`AWLEVEL`) | Completions, 2022–23 awards (`C2023_A`) | Small-institution award counts, the right-skewed, non-negative integer series used to demonstrate Poisson/negative-binomial fitting, see crosswalk above ([C2023_A dictionary](https://nces.ed.gov/ipeds/datacenter/data/C2023_A_Dict.zip)) |
| `UNDUP`/`FTE12MN` versus `EFTOTLT` | 12-Month Enrollment, 2022–23 (`DRVEF122023`) vs. EF, fall 2023 | The 12-month unduplicated headcount runs well above the fall census at institutions serving part-year students; comparing the two distributions on the same axes is the cleanest available illustration that "enrollment" is a definition, not a number, see crosswalk above ([DRVEF122023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVEF122023_Dict.zip)) |
| `LEXP100K`, `LILSYN`, `LCOLELYN` gating `LEXPTOT`, `LSTOTAL`, `LTCLLCT` | Academic Libraries, FY2023 (`AL2023`) | Screener flags that structurally determine whether expenditure, staffing, and collection fields are populated at all — the guidebook's worked example of missing-not-at-random data that is genuinely not-applicable rather than unreported, to be contrasted with the `X`-prefixed imputation flags ([AL2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/AL2023_Dict.zip)) |

### 03_classical_inference.ipynb — cross-sector retention comparison

| Variable | Survey file | Description |
|---|---|---|
| `RET_PCF`, `RET_PCP` | EF, fall 2023 (`EF2023D`) | Full-time and part-time first-year retention rate, the two-sample/ANOVA test targets, see crosswalk above ([EF2023D data](https://nces.ed.gov/ipeds/datacenter/data/EF2023D.zip), [EF2023D dictionary](https://nces.ed.gov/ipeds/datacenter/data/EF2023D_Dict.zip)) |
| `RRFTCT`, `RRFTEX`, `RRFTIN`, `RRFTCTA` (with `GRCOHRT`, `PGRCOHRT` for context only) | EF (`EF2023D`) | Full-time fall 2022 cohort, exclusions, study-abroad inclusions, and adjusted cohort: the denominator of `RET_PCF`, used as cohort size and weight. `GRCOHRT` is the fall 2023 full-time first-time cohort, a different and later group, and it is not reported by less-than-2-year institutions |
| `CONTROL`, `SECTOR` | IC | Grouping variables for the ANOVA/Kruskal–Wallis sector comparison |

### 04_bayesian_shrinkage.ipynb — small-institution graduation-rate shrinkage

| Variable | Survey file | Description |
|---|---|---|
| Adjusted cohort (`BAAC150` bachelor's / `L4AC150` less-than-4-year) and completers within 150% of normal time (`BANC150` / `L4NC150`), FY2023 (`GR200_23`); derived rate `GRRTTOT` (`DRVGR2023`) | Graduation Rates (GR) | Numerator/denominator pair for the beta-binomial hierarchical model ([GR200_23 dictionary](https://nces.ed.gov/ipeds/datacenter/data/GR200_23_Dict.zip); [DRVGR2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVGR2023_Dict.zip)) |
| `GRTYPE`, `SECTION`, `COHORT` (native `GR2023` long-format keys) | GR | Distinguishes bachelor's (150%-of-4-year) vs. less-than-4-year (150%-of-2-year) cohort types so pooling is done within, not across, normal-time definitions ([GR2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/GR2023_Dict.zip)) |
| `EFTOTLT` | EF | Institution size, used as the exposure/prior-strength covariate in partial pooling |

### 05_clustering_peer_groups.ipynb / 06_pca_institutional_landscape.ipynb — multi-block institutional feature table

| Variable | Survey file | Description |
|---|---|---|
| `ICLEVEL`, `CONTROL`, `SECTOR` | IC | Categorical anchors used to sanity-check cluster/PC assignments against known typologies |
| `EFTOTLT`, `STUFACR` | EF | Size and staffing-intensity features |
| Tuition and fees (`F1B01`/`F2D01`/`F3D01`) and instruction/academic support/institutional support expenses (`F1C011`+`F1C051`+`F1C071` GASB; `F2E011`+`F2E041`+`F2E061` FASB nonprofit; `F3E011`+`F3E03A1`+`F3E03C1` FASB for-profit) — FY2023 codes, see crosswalk above | F | Revenue-mix and cost-structure features ([DRVF2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVF2023_Dict.zip)) |
| `STAFFCAT`, `OCCUPCAT`, `FTPT` with `HRTOTLT` | HR, Fall 2023 (`S2023_OC`) | Occupational category, full-/part-time status, and staff headcount, pivoted into a staffing-mix share vector (share of staff who are instructional, management, office support, and so on), see crosswalk above ([S2023_OC dictionary](https://nces.ed.gov/ipeds/datacenter/data/S2023_OC_Dict.zip)) |
| `FACSTAT` with `SISTOTL` (and `SISPROF` through `SISNORK` by rank) | HR, Fall 2023 (`S2023_SIS`) | Faculty and tenure status crossed with rank, aggregated into a tenure-density feature (tenured and tenure-track share of full-time instructional staff) ([S2023_SIS dictionary](https://nces.ed.gov/ipeds/datacenter/data/S2023_SIS_Dict.zip)) |
| `SFTEINST`, `SFTERSRC`, `SFTEPBSV`, `SFTEMNGM`, `SFTEOFAS`, `SFTETOTL` | HR derived (`DRVHR2023`) | Pre-computed FTE by occupational function, from which mission-allocation and administrative-intensity ratios are built without re-aggregating the long file |
| `SALTOTL`, `SALPROF`, `SALASSC`, `SALASST` | HR derived (`DRVHR2023`) | Average 9-month-equated instructional salary overall and by rank, a compensation-level feature |
| `LEXPTOTF`, `LTOTLFTE`, `LEBOOKSP`, `LEXMSCSP` | Academic Libraries, FY2023 (`DRVAL2023`) | Library expenditures per FTE, library staffing, electronic-book share of collection, and subscription share of spending — library-intensity features, available only for degree-granting institutions with expenditures over $100,000 (`LEXP100K`), which makes library variables a structurally-missing block that clustering must handle explicitly |

### 07_regression_enrollment_finance.ipynb — predicting enrollment and revenue

| Variable | Survey file | Description |
|---|---|---|
| `EFTOTLT` (current + lagged years) | EF | Regression target (next-year enrollment) and lagged predictor |
| `APPLCN`, `ADMSSN`, `ENRLT` (and `-M`/`-W` gender splits) | Admissions (ADM), fall 2023 (`ADM2023`) | Applicants, admits, and enrolled counts, from which admit rate and yield are engineered as predictors, see crosswalk above ([ADM2023 data](https://nces.ed.gov/ipeds/datacenter/data/ADM2023.zip), [ADM2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/ADM2023_Dict.zip)); pre-computed equivalents `DVADM01` (admit rate) and `DVADM04` (yield) are available directly on `DRVADM2023` |
| `SATVR25`, `SATVR75`, `SATMT25`, `SATMT75`, `ACTCM25`, `ACTCM75` | ADM (`ADM2023`) | 25th/75th-percentile SAT and ACT scores, selectivity predictors |
| Tuition and fees (`F1B01` GASB / `F2D01` FASB nonprofit / `F3D01` FASB for-profit), FY2023 | F | Regression target (net tuition revenue) ([F2223_F1A dictionary](https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A_Dict.zip)) |
| `UAGRNTP`, `UPGRNTP` | Student Financial Aid (SFA), 2022–23 aid year (`SFA2223`) | Percent of all undergraduates awarded any grant aid and percent awarded Pell grants, price/affordability predictors, see crosswalk above ([SFA2223 data](https://nces.ed.gov/ipeds/datacenter/data/SFA2223.zip), [SFA2223 dictionary](https://nces.ed.gov/ipeds/datacenter/data/SFA2223_Dict.zip)) |

### 08_classification_completion_risk.ipynb — predicting completion/outcome risk

| Variable | Survey file | Description |
|---|---|---|
| `CONTROL`, `SECTOR`, `ICLEVEL` | IC | Categorical predictors |
| `APPLCN`, `ADMSSN` (admit-rate ratio), or precomputed `DVADM01` | ADM, fall 2023 (`ADM2023`/`DRVADM2023`) | Selectivity predictor |
| `UAGRNTP`, `UPGRNTP` (all-UG cohort), `PGRNT_P`, `AGRNT_A`, `FGRNT_A` (FTFT cohort) | SFA, 2022–23 aid year (`SFA2223`) | Aid-coverage-rate and average-aid-amount predictors, see crosswalk above ([SFA2223 dictionary](https://nces.ed.gov/ipeds/datacenter/data/SFA2223_Dict.zip)) |
| `FACSTAT` with `SISTOTL` (tenured/tenure-track share), and `SFTEINST`/`SFTETOTL` (instructional share of FTE) | HR, Fall 2023 (`S2023_SIS`, `DRVHR2023`) | Faculty tenure-density and instructional-staffing-intensity predictors, see crosswalk above ([S2023_SIS dictionary](https://nces.ed.gov/ipeds/datacenter/data/S2023_SIS_Dict.zip); [DRVHR2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVHR2023_Dict.zip)) |
| `PCTE12DEEXC`, `E12UG1ST`, `UNDUPUG` | 12-Month Enrollment, 2022–23 (`DRVEF122023`) | Exclusively-distance-education share, first-time degree-seeking headcount, and total undergraduate 12-month headcount — modality and scale predictors that capture part-year and online students the fall census misses |
| Graduation rate (`GRRTTOT`, `DRVGR2023`) or Outcome Measures 8-year award rate `OMAWDP8` (raw, `OM2023`) / `OM1TOTLAWDP8` (FTFT subcohort, `DRVOM2023`) | GR or OM, 2023 cohort files, see crosswalks above | Binary/ordinal classification target (above/below sector-median completion), with `OM1PELLAWDP8`/`OM1NPELAWDP8` available as a Pell-status-stratified alternative target ([OM2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/OM2023_Dict.zip); [DRVOM2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVOM2023_Dict.zip)) |

### 09_longitudinal_panel_models.ipynb — multi-year panel trends

| Variable | Survey file | Description |
|---|---|---|
| `EFTOTLT`, `RET_PCF` (year-over-year series) | EF (`EF2023A`/`EF2023D`, and prior-year vintages) | Enrollment- and retention-trend series, panel outcome variables |
| Tuition and fees (`F1B01`/`F2D01`/`F3D01`, year-over-year series) | F | Revenue-trend series |
| Graduation rate (`GRRTTOT` overall, `BAGR150`/`L4GR150` by program-length cohort, year-over-year) | GR | Completion-trend series |
| `CTOTALT` summed to institution level, by degree level (`ASCDEG`/`BASDEG`/`MASDEG`, year-over-year) | Completions (`C2023_A`/`DRVC2023`, and prior-year vintages) | Award-volume and degree-mix trend series, see crosswalk above |
| `TUFEYR0`, `TUFEYR1`, `TUFEYR2`, `TUFEYR3` | IC derived (`DRVIC2023`) | A pre-built 2020–21 through 2023–24 published-price series on a single row — used as the worked example of a wide-to-long reshape, and as a validation check against the same series assembled manually from four `IC*_AY` vintages, see crosswalk above ([DRVIC2023 dictionary](https://nces.ed.gov/ipeds/datacenter/data/DRVIC2023_Dict.zip)) |
| `UNDUP`, `FTE12MN`, `PCTE12DEEXC` (year-over-year) | 12-Month Enrollment (`DRVEF122023`, and prior-year vintages) | 12-month headcount, FTE, and exclusively-online share — the series that captures the post-2020 shift to distance education, which the fall census understates |
| `LEBOOKSP`, `LPBOOKSP`, `LEXMSCSP`, `LEXPTOTF` (year-over-year) | Academic Libraries (`DRVAL2023`, and prior-year vintages) | Print-to-digital collection transition and subscription-spending share — a strongly monotonic trend that makes a good first structural-break exercise |
| `UNITID` × academic year | All | Panel index (entity × time) for fixed/random-effects and growth-curve models |

### 10_benchmarking_scorecards.ipynb — composite peer benchmarking

| Variable | Survey file | Description |
|---|---|---|
| Cluster/peer-group label from `05_clustering_peer_groups.ipynb` | Derived | Peer-group assignment used as the benchmarking reference set |
| `EFTOTLT`, `RET_PCF`, `STUFACR`, tuition and fees (`F1B01`/`F2D01`/`F3D01`), graduation rate (`GRRTTOT`) | EF (`EF2023A`/`EF2023D`/`DRVEF2023`), F, GR | Standardized (z-scored) inputs to the composite scorecard index |
| `CHG2AY3`/`CHG3AY3` (published in-state/out-of-state price) and `CINSON`/`COTSON` (total price on campus) | IC, 2023–24 (`IC2023_AY`/`DRVIC2023`) | Published-price and total-cost-of-attendance scorecard dimensions, kept distinct from Finance-side net tuition revenue, see crosswalk above ([IC2023_AY dictionary](https://nces.ed.gov/ipeds/datacenter/data/IC2023_AY_Dict.zip)) |
| `SALTOTL`, `SFTEINST`/`SFTETOTL`, `SAEQ9AM` vs. `SAEQ9AW` | HR (`DRVHR2023`, `SAL2023_IS`) | Compensation level, instructional-staffing intensity, and the men-versus-women 9-month-equated average salary gap — an equity dimension of the scorecard ([SAL2023_IS dictionary](https://nces.ed.gov/ipeds/datacenter/data/SAL2023_IS_Dict.zip)) |
| `OMAWDP8` and `OM1PELLAWDP8` vs. `OM1NPELAWDP8` | OM (`OM2023`/`DRVOM2023`) | Eight-year award rate plus the Pell/non-Pell completion gap, which credits institutions that serve lower-income students well rather than penalizing them for their intake |
| `LEXPTOTF` | AL, FY2023 (`DRVAL2023`) | Library expenditures per FTE, an academic-support-investment dimension |
| `C21BASIC`, `C21ENPRF`, `HBCU`, `TRIBAL`, `LOCALE` | `HD2023` | Mission and setting controls, so scorecards compare like with like rather than penalizing institutions for their category |
| `UNITID` | All | Row key linking every scorecard entry back to the de-identified/synthetic institution ID from Chapter 3 |

---

## Part V — Appendices
Mirrors AstroML Part IV, "Appendices."

**Appendix A — Python Environment and Reproducibility.** `environment.yml`/`requirements.txt`, containerized (Docker) build, and a Binder/JupyterHub configuration so every notebook in the guidebook runs identically for every reader, matching AstroML's companion-package philosophy. The repository layout, the `ipeds_utils` shared-module contract, the schema-lock mechanism, and the provenance manifest are specified in Part 0 of the companion volume, **Companion Jupyter Notebook Specifications**.

**Appendix B — IPEDS Data Dictionary Quick Reference.** One-page-per-component reference for IC, ADM, E12, EF, C, GR, GR200, OM, SFA, F, HR, and AL: key variables, collection season, and the chapters that use each component. The four year-anchored crosswalks in the Notebook-to-IPEDS Variable Map now cover every one of these components with exact variable codes confirmed against the official 2023–24-cycle dictionaries, so Appendix B is a navigational index over those crosswalks rather than an independent source of truth.

**Appendix B.1 — Reference-Period Reconciliation Table.** A single table listing, for every file used in the guidebook, the exact period it describes versus the collection-cycle year in its filename. Because the offsets are not uniform — `EF2023A` is a fall 2023 census, `SFA2223` is the 2022–23 aid year, `C2023_A` is the 2022–23 award year, `EFFY2023` is the July 2022–June 2023 twelve-month period, `F2223_*` is fiscal year 2023, `S2023_OC` is a November 1, 2023 payroll snapshot, `AL2023` is fiscal year 2023, and `OM2023` reports 8-year outcomes for a 2015–16 entering cohort — any panel assembled by filename year alone will silently misalign its periods. This appendix is the authoritative check against that error.

**Appendix C — De-Identification and Data-Ethics Checklist.** The Chapter 3 workflow reduced to a reusable, auditable checklist (schema-lock → imputation-flag join → suppression rule → synthetic-ID crosswalk → versioning) to be re-run whenever a new survey year is added to the corpus.

**Appendix D — Statistical and ML Methods Cheat Sheet.** One table row per chapter: method family, assumptions, IPEDS variables it was demonstrated on, and the corresponding notebook filename.

**Appendix E — Glossary.** UNITID, imputation flag, revision flag, reporter status, Title IV, Carnegie Classification, and the twelve survey-component acronyms (IC, ADM, E12, EF, C, GR, GR200, OM, SFA, F, HR, AL) as defined by [NCES](https://nces.ed.gov/ipeds/survey-components) and the [IPEDS Data Collection System](https://www.csn.edu/sites/default/files/pdf_file/0034/158893/IPEDS-Data-Collection-System.pdf).


**Appendix F — Empirical Findings from the Analysis Notebooks.** Results from executing all ten analysis notebooks against the 2023-24 IPEDS collection cycle (files from the [IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx)). They are recorded here so each chapter can cite a concrete, reproducible number, and so readers can confirm that their own run matches. Values will shift slightly when NCES issues revised releases. The analytic universe is the 5,988 currently active institutions in IPEDS sectors 1 to 9, drawn from 6,163 directory records.

| Notebook | Chapter | Finding | Lesson for the chapter |
|---|---|---|---|
| `01_ingest_clean_deidentify` | 3 | State + sector + exact headcount re-identifies 93.3% of institutions. State + sector + size band re-identifies 6.6%, and region + sector + size band 1.2%. Adding exact retention raises the last to 35.8%; a retention band gives 9.5%. In a Colorado demographic table, primary suppression alone leaves 40 groups recoverable by subtraction. Complementary suppression (443 cells) leaves none, and it flags 17 groups whose only cell is the total | Coarsening, not removing names, is what protects a public release, and one precise outcome variable can undo it. Primary suppression without complements only looks protective |
| `02_distributions_and_missingness` | 4 | Net tuition revenue has skewness 8.85, against 0.06 after a log transform. Summing every Completions row gives 10.8 million awards against 5.3 million first-major totals. Award counts are overdispersed 159.5-fold relative to Poisson (negative-binomial alpha 0.37), and the size elasticity falls from 0.91 to 0.77 once that is modelled. 368 institutions enroll fewer students over twelve months than in fall | Model finance on the log scale, read totals at their documented grain, and never assume Poisson for institutional counts. Some apparent anomalies are definitional |
| `03_classical_inference` | 5 | Mean first-year retention: for-profit 63.7 (n = 92), nonprofit 75.0 (n = 1,136), public 74.1 (n = 627). For-profits differ from both others by a medium effect (Cliff's delta -0.34 and -0.32). Nonprofit vs public is significant on ranks (Holm p = 0.011) but negligible in size (delta 0.07), and a permutation test on means gives p = 0.20. Weighting by students rather than institutions raises the public and nonprofit means by 7.9 and 6.7 points and lowers the for-profit mean by 2.6 | Report effect sizes beside p-values. Say whether the unit of inference is the institution or the student, because the answer can flip |
| `04_bayesian_shrinkage` | 6 | 65.4% of 1,965 institutions fall outside 99.8% binomial funnel limits around the pooled bachelor's rate of 0.641, so the variation is real, not only noise. Beta-binomial priors by control are worth about five students. The raw top 10 has a median cohort of 1; after shrinkage the median cohort is 1,634, with no overlap between the two lists. Predicting the separate 2017 cohort's rate, shrinkage cuts RMSE by 15.5% for cohorts under 25 and by 12.1% overall (0.138 to 0.121) | Rank small institutions on posterior means with intervals. Validate shrinkage out of sample, not by how its rankings look |
| `05_clustering_peer_groups` | 7 | Of 2,773 four-year institutions, 2,143 have complete features. Silhouette is flat at about 0.14 for k ≥ 3, and GMM BIC has no clear minimum, so k = 8 is a judgement. Bootstrap stability is high (median ARI 0.90). Agreement is 0.39 with GMM, 0.23 with control, and 0.11 with Carnegie class. Adding the structurally missing library block moves the partition to ARI 0.67 | Peer groups are defensible but not discovered. Report stability, algorithm sensitivity, and missing-data sensitivity with any peer set |
| `06_pca_institutional_landscape` | 8 | Parallel analysis keeps three components (62% of variance). The fourth has eigenvalue 1.015, below the 1.057 noise threshold, though it passes the eigenvalue-one rule. PC1 is resources and selectivity; PC2 is scale without wealth. Bootstrap loading congruence is at least 0.956 at the 5th percentile. PC1 correlates 0.59 with bachelor's completion and 0.50 with retention, while PC2 is near zero | Use parallel analysis rather than the eigenvalue-one rule. Institutional "size" and "resources" are separate dimensions, and only resources track outcomes |
| `07_regression_enrollment_finance` | 9 | In log net tuition revenue for 1,665 institutions, R-squared is 0.911, the enrollment elasticity 1.04, and the price elasticity 0.75. Admit rate and Pell share are not significant. Cross-validated RMSE is 0.217 for OLS, ridge, and lasso, 0.213 for gradient boosting, and 0.733 for the baseline. 43% of institutions report no SAT (91% of for-profits), and SAT improves RMSE by 0.001 among reporters. The yield coefficient changes sign between samples | A well-specified linear model is hard to beat. Test-optional missingness is informative, so a complete-case analysis changes the population, not just n |
| `08_classification_completion_risk` | 10 | The target is above or below the sector median for 3,492 institutions, at the institution level only. AUC is 0.758 for logistic regression (Brier 0.200) and 0.811 for gradient boosting (0.176). False-negative rates by Pell tercile are 0.16, 0.39, and 0.51. Dropping the grant features lowers AUC to 0.773, leaves the high-Pell false-negative rate near 0.50, and miscalibrates that group (0.435 predicted vs 0.351 observed) | Removing a sensitive feature does not remove its signal. Audit error rates and calibration by subgroup, and do not use these models to score students |
| `09_longitudinal_panel_models` | 11 | Six stacked fall-enrollment vintages (EF2018D to EF2023D) pass period checks. Of 3,368 institutions, 2,732 form a balanced panel. Against the fall-2018 cohort, public 4-year retention falls 1.95 points for fall 2020 and recovers by fall 2022 (+0.08). Public 2-year retention dips earlier (-1.42 for fall 2019) and ends 2.09 points above baseline. Nonprofits are flat (-0.6 to -0.8). For-profit 4-year retention falls about 5 points (-4.63, -5.38) with wide intervals. Median annual tuition growth from 2020-21 to 2023-24 is 3.0% for nonprofit 4-year, 1.8% for public 4-year, and 1.2% for public 2-year institutions; 15.4% of publics froze tuition | Retention in release t describes the cohort that entered in fall t − 1. Compare balanced and unbalanced panels before interpreting a trend |
| `10_benchmarking_scorecards` | 12 | For focal institution 126562 (CU Denver/Anschutz), 207 of the 227 institutions in its data-driven peer group meet the four-of-six indicator rule. Across 500 random indicator weightings, the median rank correlation with equal weights is 0.91, but the 5th percentile is 0.35, and the median 90% rank interval spans 100 of 207 places. The focal rank is 189 (interval 97 to 201). Retention is 71 vs a peer median of 91, and completion within eight years is 50 vs 84. Core expenses per FTE are $189,906 vs $84,367, reflecting the medical campus | Composite ranks are driven by weight choices. Publish rank intervals, and check that resource-based peers also match the student body |

**Appendix F.1 — Data-quality lessons from execution.** Each of these produced plausible but wrong numbers until a validation check caught it, and each is now handled once in the shared `ipeds_utils` package:

- **Blank finance totals.** Finance summary lines can be blank for parent/child reporters. `F3B01` was blank for 1,592 of 2,090 for-profit filers. The part-level totals (`F1B27`/`F1C191`, `F2D16`/`F2E131`, `F3D09`/`F3E071`) are used instead, as the [IPEDS 2022-23 Finance form](https://nces.ed.gov/ipeds/use-the-data/download-survey-material/2022/finance/package_5_12.pdf) defines them. This raised tuition-share coverage from 3,498 to 5,697 institutions.
- **Duplicated library values.** 273 `DRVAL2023` institutions have no library report of their own, and each exactly repeats another institution's values. They are flagged and blanked.
- **Empty code labels.** Masking reserved codes promoted integer code columns to float, so code labels failed to match and every decoded label was empty. Decoding now fails loudly on unresolved codes.
- **Two cohorts share one file.** In `EF2023D`, `GRCOHRT` is the fall 2023 full-time first-time cohort (the current-year GRS cohort), while `RET_PCF` is computed on the full-time fall 2022 adjusted cohort `RRFTCTA`, per the [EF2023D dictionary](https://nces.ed.gov/ipeds/datacenter/data/EF2023D_Dict.zip). Neither is the 2017 or 2020 entering cohort tracked in `GR2023`. `GRCOHRT` is reported by 3,132 institutions against 5,354 for the retention cohort, and by no less-than-2-year institutions. The notebooks therefore size and weight retention by `RRFTCTA`: `03` uses it for the minimum-cohort filter and the student-weighted means, and `09` carries it through the stacked panel for its cohort-weighting exercise. `GRCOHRT` is loaded but used in no analysis.
- **Tuition history is wide.** `IC2023_AY` carries four years of published tuition as `CHG2AY0` (2020-21) to `CHG2AY3` (2023-24) rather than as separate yearly files, so the panel reshapes it from wide to long.
- **Silent de-identification passes.** De-identification functions that silently skipped absent columns now raise errors. A privacy check that passes because its input is missing is worse than no check.
---

## Cross-Cutting Design Principles

- **One dataset, one notebook, one exercise per chapter** — the same atomic unit AstroML uses, so instructors can assign chapters independently.
- **Every notebook begins from the de-identified, versioned output of Chapter 3**, never from an unprocessed raw download, so cleaning logic is centralized and auditable rather than duplicated per chapter.
- **Every prediction or clustering exercise ships with a held-out evaluation year** (train on years t−k…t−1, evaluate on year t) to teach temporal generalization, which is the institutional-research analogue of AstroML's held-out test-set discipline.
- **Statistical rigor before machine learning** — Part II (probability, classical inference, Bayesian inference) must precede Part III's clustering, regression, and classification chapters, exactly as in the source text, so that model evaluation in later chapters is grounded in the hypothesis-testing and uncertainty vocabulary taught earlier.
