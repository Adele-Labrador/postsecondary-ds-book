# Mining IPEDS Data — Executable Starter Code

Working code for the companion notebook specifications (version 1.1.0; the guidebook framework and the specifications themselves are in `docs/guidebook/`): a shared utility
package, twelve component curation notebooks, ten analysis notebooks that follow the
guidebook chapters, and a test suite. Every notebook in this repository has been executed
end to end against the live IPEDS Data Center, and every variable name has been verified
against the official published dictionaries.

## Quick start

```bash
conda env create -f environment.yml && conda activate ipeds-mining   # or: pip install -r requirements.txt
PYTHONPATH=src python -m pytest tests/ -q    # 44 tests, a few seconds offline
jupyter lab notebooks/c01_ic.ipynb           # start with the directory spine
```

Run `c01_ic` first. It produces the institutional spine that the other eleven component
notebooks join against. Then run the analysis notebooks in order. `01` builds the analytic
table that `02`-`10` read, `04` and `05` write inputs for `10`, and `05` writes the peer
groups that `06` uses if present.

Supports Python 3.10-3.12, matching the parent repository, with pandas 2.1 or later and
matplotlib 3.10 or later. The analysis dependencies are also available as
`pip install -e ".[analysis]"`. The saved notebook outputs come from Python 3.14.3 with
pandas 3.0.5, numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, statsmodels 0.15.0, and
matplotlib 3.11.2. All 22 notebooks were also run from a clean download in three further
environments:

| Environment | Result |
|---|---|
| Python 3.12, newest packages (pandas 3.0.6, scikit-learn 1.9.1) | Identical outputs |
| Python 3.10, newest packages it supports (pandas 2.3.3, scikit-learn 1.7.2) | Identical except `06`-`08`, below |
| Python 3.10, declared minimums (pandas 2.1.0, numpy 1.24.0, scipy 1.11.1, scikit-learn 1.3.0, statsmodels 0.14.0, matplotlib 3.10.0) | Identical except `06`-`08`, below |

With scikit-learn older than 1.9, gradient-boosting and logistic-regression results move in
the third decimal. Boosting RMSE in `07` is 0.214 instead of 0.213. False-negative rates by
Pell tercile in `08` are 0.17/0.38/0.53 instead of 0.16/0.39/0.51. Two tied loadings in `06`
print in a different order. No conclusion in the notebooks changes. The component notebooks
and `01`-`05`, `09`, and `10` match exactly.

The `ipeds-mining` workflow in `.github/workflows/` runs the offline tests on Python 3.10,
3.11, and 3.12, plus a 3.10 job resolved to the declared minimums. It also checks that every
committed analysis notebook matches its source in `tools/analysis_cells/`
(`python tools/build_analysis_notebooks.py --check`).

## Layout

```
src/ipeds_utils/     shared package — the only place parsing quirks are handled
  fetch.py           retrieval, unzipping, SHA-256 provenance
  dictionary.py      Excel dictionary parsing, reference-period assertions
  schema.py          CSV loading, schema locking, imputation flags, decoding
  validate.py        declarative rule harness with persistable reports
  deidentify.py      suppression, HMAC pseudonymisation, k-anonymity
  io.py              curated Parquet output with metadata sidecars
  features.py        analytic institution table, vintage stacking, peer features
  stats.py           robust z, Cliff's delta, beta-binomial shrinkage, FE transform
notebooks/           c01..c12 component notebooks, 01..10 analysis notebooks, manifest.json
tools/
  build_notebooks.py           regenerates the twelve component notebooks
  build_analysis_notebooks.py  regenerates the ten analysis notebooks
  analysis_cells/              one module of cells per analysis notebook (nb01..nb10)
tests/               44 tests (offline + network-marked)
data/
  raw/               cached downloads (git-ignored; re-fetched on demand)
  curated/           one Parquet table per component
  analytic/          institutions_2023, shrunk_grad_rates, peer_groups
  public/            coarsened, pseudonymised public-release layer
schemas/             locked column signatures, one JSON per table
reports/
  validation/        per-component and analytic-table validation reports
  figures/           figures saved by the analysis notebooks
  scorecards/        benchmarking scorecards from notebook 10
docs/
  analytic_dictionary.csv   every analytic column with its source table and variable
  provenance/               retrieval records with digests
```

The notebooks are generated, not hand-written. Editing the cell skeleton in
`tools/build_notebooks.py` updates all twelve, which is what keeps them consistent as the
guidebook evolves. Regenerate with `python tools/build_notebooks.py`.

## What each notebook does

Twelve cells, identical in structure across components: environment, retrieve, **verify
the reference period**, inspect the dictionary, load and lock the schema, mask reserved
missing codes, carry the imputation flags, decode categoricals, reshape to the declared
grain, validate, write the curated table, exercises.

| Notebook | Component | Reference period | Grain | Curated rows |
|---|---|---|---|---|
| `c01_ic` | Directory, institutional characteristics | 2023–24 universe | `UNITID` | 6,163 |
| `c02_adm` | Admissions and test scores | Fall 2023 | `UNITID` | 1,972 |
| `c03_e12` | Twelve-month enrollment | Jul 2022 – Jun 2023 | `UNITID` × `EFFYALEV` | 116,437 |
| `c04_ef` | Fall enrollment, retention, S:F ratio | Fall 2023 census | `UNITID` × `EFALEVEL` | 115,156 |
| `c05_c` | Completions by program | 2022–23 award year | `UNITID` × `CIPCODE` × `AWLEVEL` × `MAJORNUM` | 303,460 |
| `c06_gr` | Graduation rates, 150% | 2017 cohort (4-yr), 2020 (2-yr) | `UNITID` × `GRTYPE` | 51,368 |
| `c07_gr200` | Graduation rates, 200% | 2015 cohort (4-yr), 2019 (<4-yr) | `UNITID` | 4,954 |
| `c08_om` | Outcome measures | 2015–16 cohort at 4/6/8 yrs | `UNITID` × `OMCHRT` | 47,342 |
| `c09_sfa` | Student financial aid, net price | 2022–23 aid year | `UNITID` | 5,653 |
| `c10_f` | Finance, three standards | FY2023 | `UNITID` | 5,772 |
| `c11_hr` | Human resources, staffing, tenure | Payroll Nov 1, 2023 | `UNITID` × `STAFFCAT` | 180,266 |
| `c12_al` | Academic libraries | FY2023 | `UNITID` | 3,695 |

Row counts are from an actual execution of this repository against the 2023–24 collection
cycle. They will differ once NCES issues revised releases, which is the point of the
provenance digests.

## Analysis notebooks

Each is generated from `tools/analysis_cells/nbNN.py` by `python tools/build_analysis_notebooks.py`
(optionally with notebook numbers, such as `04 05`). The build parses every code cell before
writing, so a syntax error fails the build rather than the reader.

| Notebook | Guidebook | Question | Key result on the 2023-24 data |
|---|---|---|---|
| `01_ingest_clean_deidentify` | Ch. 3 | Build, validate, and de-identify one analytic table | 5,988 institutions in the universe. State + sector + exact headcount re-identifies 93% of institutions; region + sector + size band, 1.2% |
| `02_distributions_and_missingness` | Ch. 4 | How heavy are the tails, and what is missing by design? | Net tuition skewness 8.85 raw vs 0.06 in logs. Award counts are overdispersed 160-fold relative to Poisson |
| `03_classical_inference` | Ch. 5 | Does retention differ by control? | For-profit vs others: medium effect (Cliff's delta about -0.33). Nonprofit vs public: significant on ranks, negligible in size, not significant on means |
| `04_bayesian_shrinkage` | Ch. 6 | How should small cohorts be ranked? | The raw top 10 has a median cohort of 1. Shrinkage cuts out-of-cohort RMSE by 15.5% for cohorts under 25 |
| `05_clustering_peer_groups` | Ch. 7 | Can the data define peer groups? | k = 8, bootstrap ARI 0.90. Weak agreement with Carnegie class (ARI 0.11) |
| `06_pca_institutional_landscape` | Ch. 8 | How many independent dimensions? | Parallel analysis keeps 3 (62%). PC1, a resource axis, correlates 0.59 with bachelor's completion |
| `07_regression_enrollment_finance` | Ch. 9 | What predicts tuition revenue? | Enrollment elasticity 1.04, price elasticity 0.75. SAT adds nothing once size and price are known |
| `08_classification_completion_risk` | Ch. 10 | Which institutions complete above their sector median? | Institution-level only. Boosting AUC 0.81. Dropping the Pell features does not fix subgroup errors |
| `09_longitudinal_panel_models` | Ch. 11 | Did pandemic-era cohorts retain worse? | Public 4-year dip of 2 points for the fall-2020 cohort, recovered by fall 2022. Public 2-year above pre-pandemic by fall 2022 |
| `10_benchmarking_scorecards` | Ch. 12 | Where does a focal institution stand among peers? | Median 90% rank interval under random weights spans 100 of 207 places |

## The three gotchas the package exists to absorb

Each of these was hit, diagnosed, and fixed while building this code. They are handled in
`ipeds_utils` so no notebook has to think about them.

1. **Dictionary sheet and header casing varies.** Most files expose `varlist` with a
   `varname` column; `EF2023C` uses `Varlist` and the Completions dictionaries use
   `varName`. Sheet lookup and header normalisation are both case-insensitive.
2. **`openpyxl` must load dictionaries with `read_only=True`.** Several dictionaries
   contain broken embedded images that raise `KeyError: 'xl/drawings/NULL'` through the
   normal path. This is a requirement, not an optimisation.
3. **Data files carry a UTF-8 byte-order mark and lowercase headers.** The BOM attaches
   itself to the first column name, so `usecols=["UNITID"]` fails with "Usecols do not
   match columns" even though the column is plainly there. `read_csv` strips invisibles,
   matches column names case-insensitively, and falls back from `utf-8-sig` to `cp1252`.

## More gotchas found by running the analysis notebooks

Each of these produced plausible-looking wrong numbers until a check caught it.

- **Decoded labels silently became NaN.** Masking reserved codes promotes an integer column
  to float, so code `1` becomes `1.0` and no longer matches the dictionary's `"1"`. Every
  `_LABEL` column in `c01` was empty. `iu.code_key()` now canonicalises float-like codes
  (and leaves CIP codes such as `"01.0000"` untouched), and the decode cell asserts that no
  code is left unresolved.
- **CIP codes arrive as floats.** A default CSV read turns `CIPCODE` into `1.01` rather
  than `"01.0100"`. `read_csv` keeps it, `OPEID`, and `ZIP` as strings. CIP `99` rows are
  institution totals and `MAJORNUM = 2` rows are second majors. Summing every row of
  `C2023_A` gives 10,798,636 awards, against 5,299,203 from the first-major totals.
- **`"."` is a missing-value marker** in several data files, alongside the negative
  reserved codes. `read_csv` treats it as missing.
- **Finance totals: parent/child reporting.** Summary lines such as `F3B01` can be blank
  when a parent reports for itself plus its child institutions, per the
  [IPEDS 2022-23 Finance form](https://nces.ed.gov/ipeds/use-the-data/download-survey-material/2022/finance/package_5_12.pdf).
  `F3B01` was blank for 1,592 of 2,090 for-profit filers. The analytic table now uses the
  part totals (`F1B27`/`F1C191`, `F2D16`/`F2E131`, `F3D09`/`F3E071`), which raised tuition-share
  coverage from 3,498 to 5,697 institutions.
- **Library rows attributed from a parent.** `DRVAL2023` has 273 institutions with no
  `AL2023` report of their own. Each exactly repeats a reporting institution's profile.
  They are flagged `LIB_FROM_PARENT` and their library values blanked, which makes library
  missingness fully structural (`LEXP100K`).
- **Fall and twelve-month enrollment differ by design.** 368 institutions have fewer
  twelve-month than fall students (`TWELVE_TO_FALL < 1`), because the counting windows and
  student definitions differ.
- **Silent passes.** `k_anonymity` and `suppress` used to skip quasi-identifier or
  suppression columns that were absent. Both now raise `KeyError`.
- **Single-cell suppression groups.** When a group's only cell is its own total, no
  complementary cell exists. `suppress` now counts these (`groups_needing_total_suppressed`,
  17 in the Colorado demo) so the total can be suppressed too.
- **`GRCOHRT` is not the retention cohort.** In `EF2023D` it is the fall 2023 full-time
  first-time cohort (the current-year GRS cohort), while `RET_PCF` is computed on the fall
  2022 adjusted cohort `RRFTCTA`. Nor is it the cohort in `GR2023` (2017 or 2020 entrants).
  It is reported by 3,132 institutions against 5,354 for `RRFTCTA`, and by none below the
  2-year level. Weight and size retention by `RRFTCTA`.
- **Retention timing.** `RET_PCF` in the fall `t` release describes the cohort that entered
  in fall `t - 1`. `DRVGR` and `DRVEF12` exist under those names only from 2021.

## Design decisions worth knowing

**The reference period is asserted, not assumed.** Cell 3 of every notebook checks the
dictionary's Introduction sheet against the period the notebook claims to cover, and
raises if they disagree. The filename year is not the reference period and the offsets are
not uniform: `EFFY2023` covers July 2022 to June 2023, `SFA2223` is the 2022–23 aid year,
and `OM2023` reports eight-year outcomes for a cohort that entered in 2015–16. A
misaligned period is invisible in the data and corrupts every year comparison built on it.

**Reserved negative codes are masked before any arithmetic.** IPEDS encodes missingness as
`-1`, `-2`, `-3`. A mean computed without masking them is badly wrong and entirely
plausible-looking.

**A rule that cannot be evaluated counts as a failure.** If a validation rule raises —
usually because a column it references disappeared — the report marks it failed rather
than passed. Treating an unevaluable check as satisfied would hide precisely the schema
changes the harness exists to catch.

**Suppression applies to derived products, not raw tables.** IPEDS institution-level files
are already public and contain no individual records, so nothing here protects student
privacy in the raw data. The suppression and pseudonymisation tools address two other
things: re-identification risk in derived cross-tabulations, where a small institution's
completions by program by demographic group can isolate one or two students; and building
the habit on data where mistakes are cheap, for readers who will go on to handle
restricted-use files or their own registrar extracts.

**Pseudonymisation uses a keyed HMAC, not a bare hash.** There are roughly six thousand
institutions, so a plain hash of `UNITID` is inverted in seconds by hashing the whole
list. `synthetic_id` refuses to run with a placeholder salt.

## Findings from running the code

Two came out of validation failures on a real execution and are worth flagging, because
both are the kind of error that passes a spot check.

**Library expenditures include fringe benefits.** `LEXPTOT` decomposes as
`LSALWAG + LFRNGBN + LEXMSTL + LEXOMTL`, exactly, for all 2,829 institutions that report
full detail. An initial mapping that omitted `LFRNGBN` reconciled for about a third of
institutions and broke for the rest — a partial failure that a hard `sums_to` rule catches
and eyeballing does not. Those rules are error-level in `c12` for that reason.

**The twelve-month enrollment grain is `EFFYALEV`, not `EFFYLEV`.** `EFFY2023` carries 27
`EFFYALEV` level codes, with `EFFYLEV` (4 codes) and `LSTUDY` (3 codes) as coarser
rollups of the same records. The file therefore contains totals alongside their own
components, and summing across levels double-counts.

One warning is left deliberately unresolved: a single institution reports negative total
revenues in `c10_f`. That is plausible for a year of investment losses, so the rule is
`warn` rather than `error` and the value is preserved rather than masked.

## Sources

- [NCES IPEDS survey components](https://nces.ed.gov/ipeds/survey-components)
- [IPEDS Data Center complete data files](https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx)
- Distribution files and dictionaries are retrieved from
  `https://nces.ed.gov/ipeds/datacenter/data/<TABLE>.zip` and `<TABLE>_Dict.zip`
- Pedagogical model: [Statistics, Data Mining, and Machine Learning in Astronomy](https://press.princeton.edu/books/hardcover/9780691198309/statistics-data-mining-and-machine-learning-in-astronomy)
