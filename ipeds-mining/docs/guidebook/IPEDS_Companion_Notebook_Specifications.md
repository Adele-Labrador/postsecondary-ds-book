# Companion Jupyter Notebook Specifications
### Twelve Component Curation Notebooks for Mining IPEDS Data

**Companion volume to** the Mining IPEDS Guidebook Framework. Where the guidebook's ten analysis notebooks (`01`–`10`) teach statistical and machine-learning method, the twelve notebooks specified here do the unglamorous work those methods depend on: turning each raw IPEDS survey component into a validated, documented, analysis-ready table with a locked schema and an auditable provenance record.

The separation is deliberate and mirrors the pedagogy of Statistics, Data Mining, and Machine Learning in Astronomy, where catalog ingestion and cross-matching are treated as a first-class subject rather than a preamble. A reader who has not internalized that `SFA2223` and `EF2023A` describe different reference periods, or that Finance arrives in three mutually incompatible reporting standards, cannot be trusted with a random forest.

---

## Part 0 — Shared Conventions

Every specification below assumes the conventions in this section. They exist so that twelve independently-written notebooks compose into one coherent panel.

### 0.1 Repository layout

```
mining-ipeds/
├── environment.yml
├── notebooks/
│   ├── components/          c01_ic … c12_al   (this volume)
│   └── analysis/            01_ingest … 10_benchmarking  (guidebook)
├── src/ipeds_utils/         shared module (§0.2)
├── data/
│   ├── raw/                 downloaded .zip, never modified
│   ├── interim/             unzipped CSV + parsed dictionaries
│   ├── curated/             one .parquet per component  ← notebook outputs
│   └── panel/               multi-year, multi-component joins
├── schemas/                 locked schema JSON per component-year
├── reports/validation/      auto-generated validation reports
└── docs/provenance/         download manifests with URL, checksum, timestamp
```

The `raw/` directory is append-only and never edited in place. Every derived artifact must be reproducible from `raw/` by re-running notebooks in order, which is the operational definition of reproducibility used throughout the guidebook.

### 0.2 The `ipeds_utils` module

All twelve notebooks import from a single shared module rather than redefining logic. Specifying this module is part of the deliverable, because the alternative — twelve copies of a dictionary parser — is how variable-map drift begins.

| Function | Contract |
|---|---|
| `fetch(table, kind="data")` | Downloads `https://nces.ed.gov/ipeds/datacenter/data/{table}.zip` (or `{table}_Dict.zip` when `kind="dict"`) to `data/raw/`. Skips the request if the file exists and its recorded checksum matches. Appends URL, HTTP status, byte size, SHA-256, and UTC timestamp to `docs/provenance/manifest.jsonl`. |
| `unzip(table)` | Extracts to `data/interim/{table}/`. Returns both the plain and the `_RV` revised CSV paths when both are present (§0.4). |
| `read_dict(table)` | Returns a `DataFrame` of `varname`, `varTitle`, `vartype`, `imputationvar`. Must resolve the varlist sheet case-insensitively (`next(s for s in wb.sheetnames if s.lower() == "varlist")`) because NCES ships both `varlist` and `Varlist`, and must normalize the header row to lowercase because some dictionaries use `varName` where others use `varname`. Must open with `openpyxl.load_workbook(path, data_only=True, read_only=True)`; without `read_only=True` several dictionaries raise `KeyError: 'xl/drawings/NULL'` on broken embedded images. |
| `read_intro(table)` | Returns the Introduction sheet as text. Used to extract and assert the documented reference period (§0.3). |
| `lock_schema(df, table, year)` | On first run writes `schemas/{table}_{year}.json` recording column names, dtypes, null counts, and min/max per numeric column. On later runs compares and raises on any drift. This is the mechanism that catches NCES adding, renaming, or re-typing a variable between vintages. |
| `join_imputation_flags(df, table)` | Joins each `X`-prefixed flag to its measure and returns a long `(unitid, variable, value, imputation_status)` frame plus a `data_quality` tier per row. |
| `suppress(df, group_cols, count_col, threshold=15)` | Applies the guidebook's minimum-cell-size rule, masking cells below threshold and recording how many were masked. |
| `synthetic_id(df)` | Replaces `UNITID` with a salted synthetic ID, writing the crosswalk to a restricted path outside `curated/`. |
| `validate(df, rules)` | Runs a list of declarative rules and emits a Markdown + JSON report to `reports/validation/`. Raises on any rule marked `blocking=True`. |

### 0.3 Reference-period assertion

Because IPEDS filename years do not map uniformly onto the periods they describe, every notebook must assert its reference period against the file's own Introduction sheet rather than trusting the filename. This is the single most common source of silent error in IPEDS panel work.

| File family | Documented reference period |
|---|---|
| `HD2023`, `IC2023` | 2023–24 collection year / universe |
| `IC2023_AY`, `DRVIC2023` | Student charges, academic year 2023–24 |
| `ADM2023`, `EF2023A`–`EF2023D` | Fall 2023 census |
| `EFFY2023`, `EFIA2023`, `DRVEF122023` | 12 months, July 1 2022 – June 30 2023 |
| `C2023_A`/`_B`/`_C`, `DRVC2023` | Awards conferred July 1 2022 – June 30 2023 |
| `SFA2223` | 2022–23 aid year |
| `F2223_F1A`/`_F2`/`_F3`, `DRVF2023` | Fiscal year 2023 |
| `GR2023`, `DRVGR2023` | 2017 cohort at 150% of normal time |
| `GR200_23` | 2015 cohort at 200% of normal time |
| `OM2023`, `DRVOM2023` | 2015–16 entering cohort, 4/6/8-year status points (Aug 31 2019/2021/2023) |
| `S2023_OC`, `S2023_IS`, `S2023_SIS` | Payroll as of November 1, 2023 |
| `S2023_NH` | New hires November 1 2022 – October 31 2023 |
| `SAL2023_IS`, `DRVHR2023` | Academic year 2023–24 salary outlays |
| `AL2023`, `DRVAL2023` | Fiscal year 2023 |

Each notebook writes its asserted period into the curated table's Parquet metadata, so that any downstream join can be checked for period coherence programmatically.

### 0.4 Provisional versus revised releases

Several components ship both a provisional file and a `_RV` revised file (notably `C2023_A`/`_B`/`_C`, `EF2023A`, `EFFY2023`, `IC2023`). Notebooks must default to the revised file when present, record which was used in Parquet metadata, and — as a standing exercise — quantify the provisional-to-revised delta. That delta is a directly observable measure of how much confidence a same-year analysis deserves.

### 0.5 Standard cell sequence

Every component notebook follows the same twelve-cell skeleton, so a reader who has worked one can navigate all twelve:

1. Markdown header: component, files, reference period, record grain, downstream consumers.
2. Imports and configuration.
3. `fetch` + `unzip` all files for the component.
4. `read_intro` and assert the reference period.
5. `read_dict` and render the variable map as a table.
6. Load the CSV(s); report shape, dtypes, and memory.
7. `lock_schema`.
8. Reshape to the component's canonical grain.
9. `join_imputation_flags` and build the `data_quality` tier.
10. `validate` against the component's rule set.
11. Write `data/curated/{component}_{year}.parquet` with metadata.
12. Exercises.

### 0.6 Universal validation rules

Applied by every notebook in addition to its component-specific rules:

- `UNITID` is present, non-null, six digits, and joins to `HD2023` with zero orphans.
- The record grain is unique — an explicit `groupby(keys).size().max() == 1` assertion, not an assumption.
- Every institution in the curated table is `CYACTIVE` in `HD2023`, or is retained with a documented reason.
- No count variable is negative; IPEDS negative values are reserved codes and must be mapped to nulls before arithmetic.
- Totals reconcile to their parts within a stated tolerance (component-specific, §1).
- Branch-campus parent/child flags are resolved before any aggregate statistic is computed.

---

## Part 1 — The Twelve Component Notebooks

### c01_ic_institutional_characteristics.ipynb

**Files.** [HD2023](https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip), [IC2023](https://nces.ed.gov/ipeds/datacenter/data/IC2023.zip), [IC2023_AY](https://nces.ed.gov/ipeds/datacenter/data/IC2023_AY.zip), [IC2023_PY](https://nces.ed.gov/ipeds/datacenter/data/IC2023_PY.zip), [DRVIC2023](https://nces.ed.gov/ipeds/datacenter/data/DRVIC2023.zip) with matching `_Dict` files.
**Reference period.** 2023–24 collection year; charges for academic year 2023–24.
**Grain.** One row per `UNITID` (all five files are institution-level).

This notebook runs first and is the only one with no upstream dependency. It produces the institutional spine — the authoritative universe, classification, and price table that all eleven other notebooks validate against.

**Cell sequence beyond the standard skeleton.**

- Build the universe filter explicitly and report how many institutions each condition removes: `CYACTIVE`, `PSEFLAG`, `POSTSEC`, and `DEATHYR`. Emit the counts as a table. A reader should see that "all US colleges" is a choice with several defensible answers, not a given.
- Assemble the classification block: `CONTROL`, `SECTOR`, `ICLEVEL`, `HLOFFER`, `INSTSIZE`, the Carnegie 2021 triple `C21BASIC`/`C21ENPRF`/`C21SZSET`, mission flags `HBCU`/`TRIBAL`/`LANDGRNT`/`MEDICAL`, and geography `STABBR`/`FIPS`/`OBEREG`/`LOCALE`/`CBSA`.
- Assemble the price block from `IC2023_AY`: `TUITION1`/`FEE1`, `TUITION2`/`FEE2`, `TUITION3`/`FEE3` for full-time undergraduates by residency, `TUITION5`–`TUITION7`/`FEE5`–`FEE7` for graduates, published totals `CHG1AY3`/`CHG2AY3`/`CHG3AY3`, and cost-of-attendance components `CHG4AY3`–`CHG9AY3`.
- Handle the academic-year versus program-year split. Institutions on credit-hour calendars report to `IC2023_AY`; those on clock-hour programs report to `IC2023_PY`. Neither file covers the universe. Concatenate with a `charge_basis` indicator rather than silently dropping the program-year institutions, which are disproportionately for-profit and less-than-2-year — exactly the institutions whose exclusion would bias a sector comparison.
- Reshape `DRVIC2023`'s `TUFEYR0`–`TUFEYR3` from wide to long as a four-year price series, and reconcile `TUFEYR3` against `CHG2AY3` computed from `IC2023_AY`. Any institution where these disagree is a genuine data-quality finding worth reporting.

**Component validation rules.** `TUITION2 + FEE2` reconciles to `CHG2AY3` within rounding, or is flagged; `CHG2AY3 <= CHG3AY3` for public institutions (in-state price cannot exceed out-of-state), with violations listed rather than silently corrected; `SECTOR` is consistent with the `CONTROL` × `ICLEVEL` cross-tab; every `UNITID` in the price files appears in `HD2023`.

**Pitfalls.** `SECTOR` encodes control and level jointly, so including all three as separate model features introduces collinearity by construction. Institutions with `OPENADMP` set have no meaningful admissions data downstream, which explains — and must be distinguished from — missingness in `c02`.

**Outputs.** `curated/ic_2023.parquet` (spine, one row per institution), `curated/ic_price_long_2023.parquet` (four-year price series).

**Exercises.** (1) Quantify how the sector composition of the analysis universe shifts under each of four defensible universe definitions. (2) Show that excluding `IC2023_PY` institutions biases the mean published price, and by how much.

---

### c02_adm_admissions.ipynb

**Files.** [ADM2023](https://nces.ed.gov/ipeds/datacenter/data/ADM2023.zip), [DRVADM2023](https://nces.ed.gov/ipeds/datacenter/data/DRVADM2023.zip) with dictionaries.
**Reference period.** Fall 2023 entering cohort.
**Grain.** One row per `UNITID`.

**Cell sequence beyond the skeleton.**

- Load the funnel counts `APPLCN`, `ADMSSN`, `ENRLT` with their `M`/`W` gender splits, and the selectivity block `SATVR25`/`SATVR75`, `SATMT25`/`SATMT75`, `ACTCM25`/`ACTCM75`.
- Engineer admit rate (`ADMSSN / APPLCN`) and yield (`ENRLT / ADMSSN`), then reconcile against the pre-computed `DVADM01` and `DVADM04` on `DRVADM2023`. Investigate rather than average away any institution where the hand-computed and NCES-derived values differ. This reconciliation is the notebook's central teaching moment: derived files are convenient and are also a claim someone else made about your data.
- Characterize test-score missingness against the test-optional transition. Institutions reporting no SAT or ACT percentiles are not missing at random, and the notebook must show the correlation between score-reporting and `SECTOR`, selectivity, and size rather than imputing.

**Component validation rules.** `ADMSSN <= APPLCN` and `ENRLT <= ADMSSN` for every institution, blocking; the 25th percentile does not exceed the 75th for any score pair, blocking; gender parts sum to totals within tolerance; open-admission institutions (`OPENADMP` from `c01`) are excluded from admit-rate distributions rather than entering them as ratios near 1.0.

**Pitfalls.** Admissions is reported only by institutions that do not have open admissions, so the file does not cover the universe; treating absence as zero applications would be a severe error. Some institutions report applicants but not test scores, so the two blocks have different effective universes.

**Outputs.** `curated/adm_2023.parquet` with `admit_rate`, `yield_rate`, and a `selectivity_reported` flag.

**Exercises.** (1) Model the probability that an institution reports test scores as a function of sector, size, and selectivity, and interpret the result as a missingness mechanism. (2) Compare hand-computed to NCES-derived admit rates and characterize the disagreements.

---

### c03_e12_twelve_month_enrollment.ipynb

**Files.** [EFFY2023](https://nces.ed.gov/ipeds/datacenter/data/EFFY2023.zip), [EFIA2023](https://nces.ed.gov/ipeds/datacenter/data/EFIA2023.zip), [DRVEF122023](https://nces.ed.gov/ipeds/datacenter/data/DRVEF122023.zip) with dictionaries.
**Reference period.** Twelve months, July 1 2022 – June 30 2023 — one year behind the filename.
**Grain.** `EFFY2023` is long, keyed `UNITID` × `EFFYALEV`; `EFIA2023` and `DRVEF122023` are institution-level.

**Cell sequence beyond the skeleton.**

- Decode `EFFYALEV` ("Level and degree/certificate-seeking status of student") against the dictionary's value labels before any filtering, and note `EFFYLEV` and `LSTUDY` as coarser alternatives. Selecting the wrong level code is the most common way to produce a plausible-looking but wrong enrollment figure.
- Pivot the `EFY`-prefixed counts to institution level: `EFYTOTLT`/`EFYTOTLM`/`EFYTOTLW` and the nine race/ethnicity totals `EFYAIANT`, `EFYASIAT`, `EFYBKAAT`, `EFYHISPT`, `EFYNHPIT`, `EFYWHITT`, `EFY2MORT`, `EFYUNKNT`, `EFYNRALT`.
- Handle the gender-inclusive fields `EFYGUUN` (gender unknown), `EFYGUAN` (another gender), `EFYGUTOT`, and `EFYGUKN`. Because `EFYTOTLM + EFYTOTLW` no longer necessarily equals `EFYTOTLT`, the reconciliation rule must use `EFYGUKN` — the total reported in the binary categories — as the correct denominator for any men/women share. Getting this wrong produces shares that drift below 100% at institutions using the newer categories.
- Load instructional activity from `EFIA2023`: `CDACTUA` and `CNACTUA` (undergraduate credit and clock hours), `CDACTGA` (graduate credit hours), and the `ACTTYPE` indicator. Branch on `ACTTYPE` before comparing activity across institutions, since credit and clock hours are not commensurable.
- Contrast estimated `EFTEUG`/`EFTEGD` against reported `FTEUG`/`FTEGD`/`FTEDPP`. Institutions may accept the NCES-derived FTE or substitute their own; the disagreement between the two is a reported-versus-derived case study.
- Bring in `DRVEF122023` for the pre-computed `UNDUP`, `UNDUPUG`, `E12GRAD`, `FTE12MN`, the attendance-status splits `E12FT`/`E12PT` and level-specific variants, the entry-status splits `E12UG1ST`/`E12UGTRN`/`E12UGCNT`/`E12UGNDG` with `FT`/`PT` suffixes, the demographic percentages `PCTE12*`, and the distance-education shares `PCTE12DEEXC`/`PCTE12DESOM`/`PCTE12DENON`.

**Component validation rules.** Race categories sum to `EFYTOTLT` within tolerance; `E12FT + E12PT` equals `UNDUP`; `PCTE12DEEXC + PCTE12DESOM + PCTE12DENON` sums to approximately 100 where all three are reported; `UNDUP` is greater than or equal to the corresponding fall census `EFTOTLT` from `c04` for the overwhelming majority of institutions, with exceptions listed as findings.

**Pitfalls.** The one-year-back reference period is the trap. A panel that joins `EFFY2023` to `EF2023A` on filename year silently mixes a 2022–23 twelve-month count with a fall 2023 census.

**Outputs.** `curated/e12_2023.parquet`, `curated/e12_activity_2023.parquet`.

**Exercises.** (1) Plot the 12-month-to-fall headcount ratio by sector and explain why community colleges sit highest. (2) Quantify how much the choice of FTE definition changes a per-FTE finance ratio.

---

### c04_ef_fall_enrollment.ipynb

**Files.** [EF2023A](https://nces.ed.gov/ipeds/datacenter/data/EF2023A.zip), [EF2023D](https://nces.ed.gov/ipeds/datacenter/data/EF2023D.zip), [DRVEF2023](https://nces.ed.gov/ipeds/datacenter/data/DRVEF2023.zip) with dictionaries.
**Reference period.** Fall 2023 census.
**Grain.** `EF2023A` is long, keyed `UNITID` × `EFALEVEL`; `EF2023D` and `DRVEF2023` are institution-level.

**Cell sequence beyond the skeleton.**

- Decode `EFALEVEL` and pivot `EFTOTLT`/`EFTOTLM`/`EFTOTLW` plus race detail to institution level by student level.
- Load the retention and staffing block from `EF2023D`: `RET_PCF` and `RET_PCP` (full-time and part-time retention rate), `STUFACR` (student-to-faculty ratio), the retention-cohort fields `RRFTCT`, `RRFTEX`, `RRFTIN`, `RRFTCTA` (full-time fall 2022 cohort, exclusions, inclusions, adjusted cohort), and the entering-class fields `GRCOHRT` and `PGRCOHRT`. Per the `EF2023D` dictionary, `GRCOHRT` is the fall 2023 full-time first-time cohort (the current-year GRS cohort), so it is neither the denominator of `RET_PCF` nor the cohort in `GR2023`. It is reported by 3,132 institutions against 5,354 for the retention cohort, and by no less-than-2-year institutions.
- Recompute retention from its component counts and reconcile against the reported `RET_PCF`. Retention is a ratio whose denominator is adjusted for exclusions, and reconstructing it from `RRFTCT`, `RRFTEX`, and `RRFTIN` teaches why cohort-based rates are not simple divisions.
- Add `DRVEF2023` harmonized ratios and reconcile against hand-computed equivalents.

**Component validation rules.** Retention rates lie in [0, 100]; `STUFACR` is positive and its upper tail is inspected rather than trimmed, since extreme values are usually genuine (single-program or heavily-online institutions); race categories sum to totals; the fall total reconciles to the `c03` twelve-month count directionally.

**Pitfalls.** `STUFACR` is a reported ratio, not a computed one, and its definition excludes several staff categories — it is not interchangeable with a ratio built from `c11` HR data, and the notebook should demonstrate the gap.

**Outputs.** `curated/ef_2023.parquet`, `curated/ef_retention_2023.parquet`.

**Exercises.** (1) Reconstruct `RET_PCF` from components and explain every institution where you cannot. (2) Compare `STUFACR` to an FTE-based ratio built from `c11` and characterize the systematic difference.

---

### c05_c_completions.ipynb

**Files.** [C2023_A](https://nces.ed.gov/ipeds/datacenter/data/C2023_A.zip), [C2023_B](https://nces.ed.gov/ipeds/datacenter/data/C2023_B.zip), [C2023_C](https://nces.ed.gov/ipeds/datacenter/data/C2023_C.zip), [DRVC2023](https://nces.ed.gov/ipeds/datacenter/data/DRVC2023.zip) with dictionaries.
**Reference period.** Awards conferred July 1 2022 – June 30 2023.
**Grain.** `C2023_A` is keyed `UNITID` × `CIPCODE` × `MAJORNUM` × `AWLEVEL`; `C2023_C` by `UNITID` × `AWLEVELC`; `C2023_B` and `DRVC2023` are institution-level.

**Cell sequence beyond the skeleton.**

- Load `C2023_A` and establish its four-part key. This is the largest and most granular file in the guidebook, and the notebook should measure its memory footprint and demonstrate categorical dtypes and column pruning as practical necessities rather than optimizations.
- Separate the awards-versus-students distinction explicitly. `CTOTALT` counts awards; a student earning a double major or two credentials appears more than once. `DRVC2023`'s `S`-prefixed fields (`SASCDEG`, `SBASDEG`, `SMASDEG`, `SDOCDEG`, `SCERT1A`, `SCERT1B`, `SCERT24`, `SBAMACRT`) count unique students. Sum awards to institution level, compare against the unique-student counts, and require the reader to state which denominator their research question needs.
- Use `MAJORNUM` to distinguish first from second majors, and show that summing across both double-counts.
- Aggregate CIP codes to 2-digit families for program-mix features, and note that `CIPCODE` follows the 2020 CIP taxonomy — a fact that breaks longitudinal comparison across CIP revisions and must be documented for any multi-year work.
- Load the demographic and age summaries: `C2023_B` institution totals `CSTOTLT`/`CSTOTLM`/`CSTOTLW` with race detail `CSAIANT` through `CSNRALT`, and `C2023_C` age bands `CSUND18`, `CS18_24`, `CS25_39`, `CSABV40`. Note that `C2023_B` also carries gender-inclusive undergraduate and graduate fields, requiring the same denominator care as `c03`.
- Load `DRVC2023` award counts by level: `ASCDEG`, `BASDEG`, `MASDEG`, `DOCDEGRS`, `DOCDEGPP`, `DOCDEGOT`, `CERT1` (with `CERT1A`/`CERT1B` sub-splits), `CERT2`, `CERT4`, `PBACERT`, `PMACERT`.

**Component validation rules.** `C2023_A` summed over `CIPCODE` at `MAJORNUM == 1` reconciles to `C2023_B` totals; age bands in `C2023_C` sum to `CSTOTLT`; `AWLEVEL` values are consistent with the award-offering flags `LEVEL1`/`LEVEL2`/`LEVEL3`/`LEVEL5` from `c01`; unique-student counts never exceed award counts for the same credential level.

**Pitfalls.** The awards-versus-students conflation is the dominant error in published completions analysis. The 2020 CIP taxonomy break is the dominant error in longitudinal completions analysis.

**Outputs.** `curated/c_awards_long_2023.parquet` (full grain), `curated/c_institution_2023.parquet` (institution-level with degree mix), `curated/c_cip2_mix_2023.parquet` (program-mix feature matrix).

**Exercises.** (1) Compute the ratio of awards to unique completers by sector and explain the variation. (2) Build a program-concentration index (Herfindahl over 2-digit CIP) and show its relationship to institution size.

---

### c06_gr_graduation_rates.ipynb

**Files.** [GR2023](https://nces.ed.gov/ipeds/datacenter/data/GR2023.zip), [DRVGR2023](https://nces.ed.gov/ipeds/datacenter/data/DRVGR2023.zip) with dictionaries.
**Reference period.** Graduation status as of August 31, 2023 at 150% of normal program time. The cohort year differs by institution level within this one file: the 2017 entering cohort at 4-year institutions and the 2020 entering cohort at 2-year institutions. A panel that treats `GR2023` as a single cohort year is wrong for one of the two sectors. Confirmed against the `GR2023` dictionary Introduction sheet, which titles the file "cohort year 2017 (4-year) and cohort year 2020 (2-year) institutions".
**Grain.** `GR2023` is long, keyed `UNITID` × `GRTYPE` × `SECTION` × `COHORT`; `DRVGR2023` is institution-level.

**Cell sequence beyond the skeleton.**

- Decode `GRTYPE`, `SECTION`, and `COHORT` against the dictionary before any subsetting. `GRTYPE` distinguishes cohort and outcome rows within the same file, and selecting rows without decoding it is the single most reliable way to compute a wrong graduation rate. The notebook should deliberately show a naive filter producing an implausible value, then the correct one.
- Establish that bachelor's cohorts are measured at 150% of four years while less-than-four-year cohorts are measured at 150% of two years. Pooling across these without stratifying compares different elapsed-time definitions.
- Build the cohort-and-completer table at the correct grain, then compute rates as explicit numerator-over-denominator pairs rather than reading a pre-computed rate. Reconcile against `DRVGR2023`'s `GRRTTOT` and the program-length-specific `BAGR150`/`L4GR150`.
- Preserve the numerator and denominator as separate columns in the output. Notebook `04`'s beta-binomial shrinkage model requires the counts, not the ratio, and a curated table that stores only the rate silently forecloses that entire chapter.

**Component validation rules.** Completers never exceed the adjusted cohort; recomputed rates match `DRVGR2023` within rounding tolerance, with every exception listed; cohorts of size zero produce nulls rather than division errors or zeros; institutions offering only non-degree programs are absent rather than present with zero cohorts.

**Pitfalls.** The graduation-rate cohort is first-time full-time degree-seeking students only. At institutions serving mostly part-time or transfer students it describes a small and unrepresentative minority of enrollment, which is precisely the deficiency Outcome Measures (`c08`) exists to remedy. The notebook must state this limitation plainly, since a benchmarking scorecard built on `GRRTTOT` alone systematically misrepresents open-access institutions.

**Outputs.** `curated/gr_2023.parquet` with cohort, completers, and rate columns retained separately.

**Exercises.** (1) Show what fraction of each sector's total undergraduate enrollment the GR cohort actually represents. (2) Demonstrate the bias from pooling bachelor's and less-than-four-year cohorts.

---

### c07_gr200_extended_graduation_rates.ipynb

**Files.** [GR200_23](https://nces.ed.gov/ipeds/datacenter/data/GR200_23.zip) with dictionary.
**Reference period.** Graduation status as of August 31, 2023 at 200% of normal program time, again split by institution level: the 2015 entering cohort at 4-year institutions and the 2019 entering cohort at less-than-4-year institutions. Confirmed against the `GR200_23` dictionary Introduction sheet.
**Grain.** One row per `UNITID`.

This is the shortest specification and the most pedagogically dense, because the file is a single explicit cohort-adjustment pipeline laid out across columns.

**Cell sequence beyond the skeleton.**

- Walk the bachelor's pipeline stage by stage as an audit trail: `BAREVCT` (revised cohort) → `BAEXCLU` (exclusions) → `BAAC150` (adjusted cohort at 150%) → `BANC100`/`BAGR100` (completers and rate at 100%) → `BANC150`/`BAGR150` (at 150%) → `BAAEXCL` (additional exclusions) → `BAAC200` (adjusted cohort at 200%) → `BANC200`/`BAGR200` (at 200%), with `BASTEND` accounting for students still enrolled who are neither completers nor exclusions.
- Repeat for the less-than-four-year pipeline: `L4REVCT`, `L4EXCLU`, `L4AC150`, `L4NC100`/`L4GR100`, `L4NC150`/`L4GR150`, `L4AEXCL`, `L4AC200`, `L4NC200`/`L4GR200`, `L4STEND`.
- Render the pipeline as a per-institution waterfall chart. Cohort attrition through exclusions is invisible in a published rate and visible in a waterfall, which is the point.
- Compute the 100%-to-150%-to-200% completion increment and interpret it as the value of additional time — the substantive finding this file uniquely supports.

**Component validation rules.** Monotonicity is blocking at every stage: `BANC100 <= BANC150 <= BANC200` and `BAGR100 <= BAGR150 <= BAGR200`, with the same for `L4`; adjusted cohorts decrease weakly as exclusions accumulate; `BAAC200 + BASTEND` and the completer counts are mutually consistent; the 2015 cohort here is distinct from the 2017 cohort in `c06` and the two must never be joined as though contemporaneous.

**Pitfalls.** Exclusions are legitimate (death, permanent disability, military service, foreign aid service, religious mission) but are institution-reported, so exclusion rates vary in ways that affect the denominator. An institution with an unusually high `BAEXCLU` share deserves scrutiny, and the notebook should rank institutions on it.

**Outputs.** `curated/gr200_2023.parquet` with all pipeline stages retained.

**Exercises.** (1) Rank sectors by the 150%-to-200% completion increment. (2) Test whether exclusion rates correlate with reported graduation rates in a direction suggesting reporting discretion.

---

### c08_om_outcome_measures.ipynb

**Files.** [OM2023](https://nces.ed.gov/ipeds/datacenter/data/OM2023.zip), [DRVOM2023](https://nces.ed.gov/ipeds/datacenter/data/DRVOM2023.zip) with dictionaries.
**Reference period.** 2015–16 entering cohort at 4-, 6-, and 8-year status points (August 31 2019, 2021, 2023).
**Grain.** `OM2023` is long, keyed `UNITID` × `OMCHRT`; `DRVOM2023` is institution-level and very wide.

**Cell sequence beyond the skeleton.**

- Decode `OMCHRT` into its two dimensions — attendance status (full-time, part-time) crossed with entry status (first-time, non-first-time), further split by Pell status — yielding the eight subcohorts. This file exists because the `c06` cohort excludes part-time and transfer students, and the notebook should open by quantifying how much of enrollment those excluded groups represent.
- Walk the cohort adjustment: `OMRCHRT` → `OMEXCLS` → `OMACHRT`.
- Build the award outcomes at each status point: `OMCERT4`/`OMASSC4`/`OMBACH4`/`OMAWDN4`/`OMAWDP4` and the `6` and `8` analogues.
- Build the 8-year enrollment-status detail, available only at that point: `OMENRYI` (still enrolled here), `OMENRAI` (enrolled elsewhere), `OMENRUN` (status unknown), `OMNOAWD` (no award, not known enrolled), with percentages `OMENRTP`/`OMENRYP`/`OMENRAP`/`OMENRUP`. Emphasize that `OMENRUN` is substantively different from a null — it is a measured category of ignorance, and collapsing it into "did not complete" overstates failure.
- Parse `DRVOM2023`'s systematic naming into a tidy frame rather than handling 109 columns individually. The pattern is `OM{1-4}{TOTL|PELL|NPEL}{outcome}{4|6|8}`, where `OM1` is full-time first-time, `OM2` part-time first-time, `OM3` full-time non-first-time, `OM4` part-time non-first-time; outcomes are `AWDP` (any award), `CRTP`/`ASCP`/`BACP` (certificate, associate's, bachelor's), and `ENYP`/`ENAP`/`ENUP` (enrolled here, elsewhere, unknown). Writing a regex-based column parser here is itself the exercise, and it generalizes to every wide IPEDS derived file.
- Compute the Pell versus non-Pell completion gap as `OM1PELLAWDP8 - OM1NPELAWDP8` and its analogues for subcohorts 2 through 4. This is the equity measure that feeds notebook `10`.

**Component validation rules.** Award counts are non-decreasing across the 4-, 6-, and 8-year status points, blocking; the four 8-year status categories (`OMAWDN8`, `OMENRYI`, `OMENRAI` plus `OMENRUN`, `OMNOAWD`) partition the adjusted cohort without overlap or gap; percentages recompute from counts within tolerance; the total subcohort sums to the all-students cohort; Pell and non-Pell subcohorts sum to the total.

**Pitfalls.** The 8-year outcome is measured for a cohort that entered eight years earlier, so this file describes an institution as it was in 2015–16. Treating it as a current-performance measure alongside fall 2023 enrollment is a category error that the notebook must name explicitly.

**Outputs.** `curated/om_2023.parquet` (tidy, one row per institution × subcohort × status point), `curated/om_equity_gaps_2023.parquet`.

**Exercises.** (1) Compare the `c06` graduation rate to the `OMAWDP8` award rate by sector and explain where they diverge most. (2) Build the Pell gap measure and test whether it correlates with institutional wealth from `c10`.

---

### c09_sfa_student_financial_aid.ipynb

**Files.** [SFA2223](https://nces.ed.gov/ipeds/datacenter/data/SFA2223.zip), optionally [SFAV2223](https://nces.ed.gov/ipeds/datacenter/data/SFAV2223.zip) for military and veterans' benefits, with dictionaries.
**Reference period.** 2022–23 aid year — one year behind the fall 2023 census it is collected alongside.
**Grain.** One row per `UNITID`.

**Cell sequence beyond the skeleton.**

- Establish the two-cohort structure immediately, because it is the file's defining complication. Underscore-suffixed variables describe the full-time first-time degree-seeking cohort; `U`-prefixed variables describe all undergraduates. These are different denominators and must never be mixed in one rate.

| Aid type | FTFT cohort | All undergraduates |
|---|---|---|
| Any grant aid | `AGRNT_N`/`_P`/`_T`/`_A` | `UAGRNTN`/`UAGRNTP`/`UAGRNTT`/`UAGRNTA` |
| Federal grant aid | `FGRNT_N`/`_P`/`_T`/`_A` | — |
| Pell grants | `PGRNT_N`/`_P`/`_T`/`_A` | `UPGRNTN`/`UPGRNTP`/`UPGRNTT`/`UPGRNTA` |
| State/local grants | `SGRNT_N`/`_P`/`_T`/`_A` | — |
| Institutional grants | `IGRNT_N`/`_P`/`_T`/`_A` | — |
| Any student loans | `LOAN_N`/`_P`/`_T`/`_A` | — |
| Federal loans | `FLOAN_N`/`_P`/`_T`/`_A` | `UFLOANN`/`UFLOANP`/`UFLOANT`/`UFLOANA` |

- Decode the suffix grammar once and reuse it: `N` is recipient headcount, `P` percent of the relevant cohort, `T` total dollars, `A` average dollars per recipient. Note that `T / N` should approximate `A`, giving a free internal consistency check across every aid type.
- Reconcile the FTFT aid cohort against the `c02` `ENRLT` and the `c04` retention cohort, which are related but not identical populations.
- Emphasize that only Pell, any-grant, and federal-loan measures exist for the all-undergraduate cohort. A study needing institutional-grant generosity across all undergraduates cannot have it, and the notebook should say so rather than substituting the FTFT figure.

**Component validation rules.** `T / N` approximates `A` within tolerance for every aid type, blocking; percentages lie in [0, 100]; Pell recipients never exceed any-grant recipients; the FTFT cohort size is plausible against `c02` and `c04`; `SFA2223` reference period is asserted as 2022–23, not 2023–24.

**Pitfalls.** The one-year aid lag is a documented feature of the panel and not a defect, but it must be recorded. Mixing FTFT and all-undergraduate denominators produces rates that look reasonable and are wrong.

**Outputs.** `curated/sfa_2223.parquet` with an explicit `cohort_basis` column on every rate.

**Exercises.** (1) Verify the `T`/`N`/`A` identity across all aid types and report every violation. (2) Show how a discount-rate estimate changes depending on which cohort's denominator is used.

---

### c10_f_finance.ipynb

**Files.** [F2223_F1A](https://nces.ed.gov/ipeds/datacenter/data/F2223_F1A.zip) (GASB public), [F2223_F2](https://nces.ed.gov/ipeds/datacenter/data/F2223_F2.zip) (FASB private nonprofit), [F2223_F3](https://nces.ed.gov/ipeds/datacenter/data/F2223_F3.zip) (private for-profit), [DRVF2023](https://nces.ed.gov/ipeds/datacenter/data/DRVF2023.zip) with dictionaries.
**Reference period.** Fiscal year 2023.
**Grain.** One row per `UNITID`, but partitioned across three mutually exclusive files by reporting standard.

This is the most demanding component notebook, because the same economic concept carries a different variable name in each of three accounting standards, and no single file covers the universe.

**Cell sequence beyond the skeleton.**

- Establish the partition: every institution appears in exactly one of the three files according to its accounting standard, determined by `CONTROL` from `c01`. Assert that the three sets are disjoint and that their union covers the finance-reporting universe.
- Build the harmonization crosswalk explicitly as a dictionary in code, not implicitly in a merge:

| Concept | GASB (`F1A`) | FASB nonprofit (`F2`) | For-profit (`F3`) |
|---|---|---|---|
| Tuition and fees revenue | `F1B01` | `F2D01` | `F3D01` |
| Investment / endowment income | `F1B17` | `F2D10` | `F3D05` |
| Instruction expenses | `F1C011` | `F2E011` | `F3E011` |
| Academic support expenses | `F1C051` | `F2E041` | `F3E03A1` |
| Institutional support expenses | `F1C071` | `F2E061` | `F3E03C1` |

- Stack the three standards into one long frame with a `reporting_standard` column retained on every row, so that any downstream comparison can control for it. The standards are not perfectly commensurable, and hiding which one a row came from destroys the reader's ability to reason about that.
- Add `DRVF2023` pre-computed per-FTE ratios and reconcile against hand-computed equivalents, being explicit about which FTE denominator the derived file uses — this connects directly to the `c03` reported-versus-estimated FTE question.
- Demonstrate that raw dollar amounts are unusable for cross-institution comparison without normalization, and build per-FTE and per-student versions.

**Component validation rules.** The three files are disjoint on `UNITID`, blocking; `CONTROL` from `c01` predicts which file an institution appears in, with exceptions listed; expense components do not exceed reported totals; per-FTE ratios use a documented and consistent denominator; negative values are checked against the dictionary's reserved codes before being treated as genuine negatives, since investment losses are genuinely negative while reserved codes are not.

**Pitfalls.** Comparing a GASB institution's tuition revenue to a FASB institution's without noting the standard is the classic Delta Cost Project caution. Endowment and investment income are heavy-tailed and, in loss years, genuinely negative — log transforms will fail and must be handled, not suppressed.

**Outputs.** `curated/f_harmonized_2023.parquet` (long, with `reporting_standard`), `curated/f_ratios_2023.parquet`.

**Exercises.** (1) Show the distributional consequence of ignoring `reporting_standard` when comparing tuition dependence across sectors. (2) Fit a log-normal to endowment per FTE and document exactly how you handled non-positive values.

---

### c11_hr_human_resources.ipynb

**Files.** [S2023_OC](https://nces.ed.gov/ipeds/datacenter/data/S2023_OC.zip), [S2023_IS](https://nces.ed.gov/ipeds/datacenter/data/S2023_IS.zip), [S2023_SIS](https://nces.ed.gov/ipeds/datacenter/data/S2023_SIS.zip), [S2023_NH](https://nces.ed.gov/ipeds/datacenter/data/S2023_NH.zip), [SAL2023_IS](https://nces.ed.gov/ipeds/datacenter/data/SAL2023_IS.zip), [SAL2023_NIS](https://nces.ed.gov/ipeds/datacenter/data/SAL2023_NIS.zip), [DRVHR2023](https://nces.ed.gov/ipeds/datacenter/data/DRVHR2023.zip) with dictionaries.
**Reference period.** Payroll as of November 1 2023; new hires November 1 2022 – October 31 2023; salary outlays academic year 2023–24.
**Grain.** `S2023_OC` keyed `UNITID` × `STAFFCAT`; `S2023_SIS` by `FACSTAT`; `S2023_NH` by `SNHCAT`; `SAL2023_IS` by `ARANK`; `DRVHR2023` institution-level.

**Cell sequence beyond the skeleton.**

- Open with the stock-versus-flow distinction, because it is the error this notebook exists to prevent. `S2023_OC` is the standing headcount of all staff as of a single date. `S2023_NH` counts only people hired during a twelve-month window. A staffing-mix or tenure-density feature requires the stock; using the new-hires file yields a hiring-composition measure that resembles a staffing measure and is not one. Compute both and show they differ substantially.
- Build the staffing mix from `S2023_OC`: decode `STAFFCAT` (occupation crossed with full-/part-time status) along with `FTPT`, `OCCUPCAT`, and `SABDTYPE`, then pivot `HRTOTLT` into occupational shares. Note that the race and gender detail (`HRTOTLM`/`HRTOTLW`, `HRAIANT` through `HRNRALT`) uses the same suffix grammar as enrollment and completions.
- Build tenure density from `S2023_SIS`: decode `FACSTAT` and pivot `SISTOTL` with the rank detail `SISPROF`, `SISASCP`, `SISASTP`, `SISINST`, `SISLECT`, `SISNORK`. Compute tenured and tenure-track share of full-time instructional staff.
- Note the reporting threshold: `S2023_IS` and `S2023_NH` cover only degree-granting institutions with 15 or more full-time staff. Tenure and new-hire measures are therefore structurally absent for small institutions, and that absence must be modeled as not-applicable rather than imputed.
- Build compensation from `SAL2023_IS`: decode `ARANK`, then load `SAINSTT`/`SAINSTM`/`SAINSTW` counts, `SAOUTLT`/`SAOUTLM`/`SAOUTLW` outlays, and the contract-length-adjusted `SAEQ9AT`/`SAEQ9AM`/`SAEQ9AW` averages with `SAEQ9OT` outlays. Insist on the 9-month-equated figures for any cross-institution comparison, since `SA09MAT`, `SA10MAT`, `SA11MAT`, and `SA12MAT` describe different contract lengths and are not comparable as-is.
- Compute the men-versus-women average salary gap from `SAEQ9AM` and `SAEQ9AW`, within academic rank. Aggregating across ranks confounds the pay gap with rank distribution, which is a distinct phenomenon, and the notebook should show both decompositions.
- Add `DRVHR2023`: average 9-month-equated salary by rank (`SALTOTL`, `SALPROF`, `SALASSC`, `SALASST`, `SALINST`, `SALLECT`, `SALNRNK`) and FTE by occupational function (`SFTETOTL`, `SFTEPSTC`, `SFTEINST`, `SFTERSRC`, `SFTEPBSV`, `SFTELCAI`, `SFTELCA`, `SFTEOTIS`, `SFTEMNGM`, `SFTEBFO`, `SFTECES`, `SFTECLAM`, `SFTEHLTH`, `SFTEOTHR`, `SFTESRVC`, `SFTESALE`, `SFTEOFAS`, `SFTENRCM`, `SFTEPTMM`).
- Build administrative-intensity and mission-allocation ratios from the `SFTE` family, noting that `SFTELCAI` aggregates `SFTELCA` and `SFTEOTIS` — summing all three double-counts.

**Component validation rules.** Occupational FTE components sum to `SFTETOTL` without double-counting the nested aggregates, blocking; staff race and gender categories sum to totals; `SAEQ9AT` recomputes from `SAEQ9OT / SATOTLT` within tolerance; tenure measures are null rather than zero for institutions below the 15-staff threshold; new-hire counts never exceed total staff counts.

**Pitfalls.** The nested aggregate structure in the `SFTE` family causes silent double-counting. The 15-staff reporting threshold is a structural-missingness mechanism correlated with sector and size. The stock-versus-flow confusion between `S2023_OC` and `S2023_NH` is the specific error this notebook is designed to foreclose.

**Outputs.** `curated/hr_staffing_2023.parquet`, `curated/hr_tenure_2023.parquet`, `curated/hr_salary_2023.parquet`.

**Exercises.** (1) Compute staffing mix from both `S2023_OC` and `S2023_NH` and quantify how misleading the latter is as a proxy. (2) Decompose the gender salary gap into a within-rank component and a rank-distribution component.

---

### c12_al_academic_libraries.ipynb

**Files.** [AL2023](https://nces.ed.gov/ipeds/datacenter/data/AL2023.zip), [DRVAL2023](https://nces.ed.gov/ipeds/datacenter/data/DRVAL2023.zip) with dictionaries.
**Reference period.** Fiscal year 2023.
**Grain.** One row per `UNITID`.

Academic Libraries is the smallest component and the guidebook's designated case study in structural missingness, because its reporting is gated by explicit screener flags rather than by non-response.

**Cell sequence beyond the skeleton.**

- Map the screener cascade before loading any measure: `LEXP100K` (were total library expenses at least $100,000) gates the expenditure block; `LILSYN` (does the institution have library staff) gates staffing; `LILLDYN` gates interlibrary loan; `LCOLELYN` (is the collection entirely electronic) determines whether physical-collection fields are meaningful; `LFRNGBYN` gates `LFRNGBN`. Render the cascade as a decision tree and tabulate how many institutions each gate removes.
- Distinguish three kinds of zero-or-blank explicitly: genuinely zero, not-applicable by screener, and not-reported. Collapsing these is the error the notebook exists to teach against, and it produces a mean library expenditure that is badly wrong in a predictable direction.
- Load collections: `LPBOOKS`, `LEBOOKS`, `LEDATAB`, `LPMEDIA`, `LEMEDIA`, `LPSERIA`, `LESERIA`, with totals `LPCLLCT`, `LECLLCT`, `LTCLLCT`.
- Load circulation `LPCRCLT`, `LECRCLT`, `LTCRCLT`, and interlibrary loan `LILLDPR`, `LILLDRC`.
- Load staffing `LSTOTAL`, `LSLIBRN`, `LSOPROF`, `LSOPAID`, `LSSTAST`, and `LBRANCH`.
- Load expenditures: `LSALWAG`, `LFRNGBN`, materials and services `LEXMSTL` with components `LEXMSBB` (one-time purchases), `LEXMSCS` (ongoing subscription commitments), `LEXMSOT`, operations and maintenance `LEXOMTL` with `LEXOMPS` (preservation) and `LEXOMOT`, plus totals `LEXPTOT` and `LSWMSOM`.
- Add `DRVAL2023` shares: collection composition `LPBOOKSP`, `LEBOOKSP`, `LEDATABP`, `LPMEDIAP`, `LEMEDIAP`, `LPSERIAP`, `LESERIAP`; expenditure composition `LSALWAGP`, `LFRNGBNP`, `LEXMSBBP`, `LEXMSCSP`, `LEXMSOTP`, `LEXOMTLP`; the normalized `LEXPTOTF` (expenditures per FTE); and staffing `LTOTLFTE`, `LLIBRFTE`, `LPROFFTE`, `LPAIDFTE`, `LSTUDFTE`.

**Component validation rules.** `LPCLLCT + LECLLCT` equals `LTCLLCT`; expenditure components sum to `LEXPTOT`; collection-composition percentages sum to approximately 100; expenditure fields are null rather than zero where `LEXP100K` indicates the institution is below threshold, blocking; `LEXPTOTF` recomputes from `LEXPTOT` and a documented FTE denominator; library data are absent for non-degree-granting institutions by design.

**Pitfalls.** Treating screener-gated nulls as zeros deflates every library mean. The electronic-only flag `LCOLELYN` makes physical-collection zeros meaningful rather than missing, which is the opposite of the usual convention and must be handled explicitly.

**Outputs.** `curated/al_2023.parquet` with an explicit `missingness_reason` column on every gated field.

**Exercises.** (1) Compute mean library expenditure per FTE three ways — treating gated nulls as zero, dropping them, and modeling them as not-applicable — and reconcile the differences. (2) Build the print-to-digital share and test whether it varies with sector and size.

---

## Part 2 — How the Twelve Feed the Ten

The component notebooks produce curated tables; the guidebook's analysis notebooks consume them. This table is the contract between the two volumes, and it should be regenerated automatically from notebook metadata so it cannot drift. All ten analysis notebooks are now implemented with executable starter cells; §3.5 summarises what each does and what it found, and `notebooks/manifest.json` records each notebook's inputs and outputs.

| Analysis notebook | Consumes |
|---|---|
| `01_ingest_clean_deidentify` | All twelve — this notebook is where the spine, suppression, and synthetic-ID layers are applied across components |
| `02_distributions_and_missingness` | `c10` (heavy-tailed finance), `c04` (student-faculty ratio), `c05` (count distributions), `c03` (12-month versus fall), `c12` (structural missingness) |
| `03_classical_inference` | `c04` (retention by sector), `c01` (grouping variables) |
| `04_bayesian_shrinkage` | `c06`, `c07` (cohort and completer counts, not rates), `c04` (size as prior strength) |
| `05_clustering_peer_groups` | `c01`, `c04`, `c10`, `c11`, `c12` (multi-block feature table) |
| `06_pca_institutional_landscape` | Same feature table as `c05`'s consumer |
| `07_regression_enrollment_finance` | `c04`, `c02`, `c10`, `c09`, `c03` |
| `08_classification_completion_risk` | `c06` or `c08` (target), `c01`, `c02`, `c09`, `c11`, `c03` (features) |
| `09_longitudinal_panel_models` | Multi-year vintages of `c04`, `c10`, `c06`, `c05`, `c01`, `c03`, `c12` |
| `10_benchmarking_scorecards` | `c01` (mission controls), `c04`, `c10`, `c06`, `c08`, `c09`, `c11`, `c12` |

### 2.1 Multi-year extension

Every specification above is written for the 2023–24 collection cycle. Extending to a panel requires only that the notebooks be parameterized by year, but three cautions govern the exercise and should be stated in each notebook's closing cell:

- **Reference-period offsets are not uniform across components.** A panel keyed on filename year silently misaligns periods. The reconciliation table in §0.3 is the authoritative check.
- **Taxonomies break.** CIP revisions (`c05`), Carnegie Classification vintages (`c01`), and the introduction of gender-inclusive categories (`c03`, `c05`) all create discontinuities that look like findings.
- **Schema drift is normal.** The `lock_schema` mechanism exists so that drift surfaces as a loud failure at ingestion rather than as a quiet anomaly in a model six notebooks later.

---

## Part 3 — Executable Implementation

This specification is implemented as a working repository: the `ipeds_utils` package, all twelve notebooks generated from a single spec table, and a test suite. Every notebook has been executed end to end against the live IPEDS Data Center and every variable name in this document has been verified programmatically against the published dictionaries.

### 3.1 Corrections that came out of execution

Writing the code falsified four claims that reading alone had left standing. They are recorded here because each is the kind of error that survives a spot check.

| Claim as specified | Corrected by execution |
|---|---|
| `GR2023` = 2017 entering cohort | 2017 at 4-year **and 2020 at 2-year** institutions, in the same file |
| `GR200_23` = 2015 entering cohort | 2015 at 4-year **and 2019 at less-than-4-year** institutions |
| `OM2023` percentages `OMENRAP8`, `OMENRYP8` | No such columns. The real names are `OMENRAI`/`OMENRYI` (counts) and `OMENRAP`/`OMENRYP`/`OMENRUP` (percentages) |
| `S2023_OC` staffing counts `SVEMP01`, `SVEMP02` | No such columns. The file uses `HRTOTLT`/`HRTOTLM`/`HRTOTLW`, with `OCCUPCAT` and `FTPT` separating the two dimensions that `STAFFCAT` bundles |

Two further findings came from validation rules failing on real data rather than from name checks:

- **`LEXPTOT` includes fringe benefits.** The decomposition is `LSALWAG + LFRNGBN + LEXMSTL + LEXOMTL`, exact for all 2,829 institutions reporting full detail. A mapping omitting `LFRNGBN` reconciles for roughly a third of institutions and breaks for the rest. The `sums_to` rules in `c12` are therefore error-level, not warnings.
- **`EFFY2023` is keyed on `EFFYALEV`, not `EFFYLEV`.** There are 27 `EFFYALEV` codes against 4 for `EFFYLEV` and 3 for `LSTUDY`; the latter two are coarser rollups of the same records, so the file holds totals beside their own components and the declared grain must be `UNITID` x `EFFYALEV`.

### 3.2 Three distribution quirks absorbed by the package

All three were hit while building and are handled once in `ipeds_utils` so no notebook contends with them.

1. **Dictionary sheet and header casing varies.** Most files expose `varlist` with `varname`; `EF2023C` uses `Varlist` and the Completions dictionaries use `varName`. Both lookups are case-insensitive.
2. **`openpyxl` requires `read_only=True`.** Several dictionaries carry broken embedded images that raise `KeyError: 'xl/drawings/NULL'` through the normal load path. This is a requirement, not a performance choice.
3. **Data files carry a UTF-8 byte-order mark over lowercase headers.** The BOM attaches to the first column name, so `usecols=["UNITID"]` fails with "Usecols do not match columns" although the column is plainly present. The reader strips invisible characters, matches names case-insensitively, and falls back from `utf-8-sig` to `cp1252`.

### 3.3 Two semantics worth stating explicitly

**An unevaluable rule counts as a failure.** If a validation rule raises — usually because a column it references has disappeared — the report marks it failed rather than passed. Treating an unevaluable check as satisfied would conceal exactly the schema changes the harness exists to detect. This was itself caught by a unit test rather than by inspection.

**Suppression belongs to derived products, not raw tables.** IPEDS institution-level files are already public and hold no individual records, so nothing in the de-identification module protects student privacy in the raw data. The tools address re-identification risk in derived cross-tabulations, where a small institution's completions by program by demographic group can isolate one or two students, and they build a habit on data where mistakes are cheap for readers who will later handle restricted-use files. Pseudonymisation uses a keyed HMAC rather than a bare hash, because roughly six thousand institutions can be enumerated and a plain hash inverted in seconds.

### 3.4 Curated output

One Parquet table per component with a metadata sidecar carrying reference period and grain, plus a per-component validation report and provenance record with SHA-256 digests. Row counts from an actual run against the 2023-24 cycle: `c01` 6,163; `c02` 1,972; `c03` 116,437; `c04` 115,156; `c05` 303,460; `c06` 51,368; `c07` 4,954; `c08` 47,342; `c09` 5,653; `c10` 5,772; `c11` 180,266; `c12` 3,695. These will shift when NCES issues revised releases, which is what the digests are for.

All twelve components validate clean except one deliberate warning: a single institution reports negative total revenues in `c10_f`, which is plausible after a year of investment losses, so the value is preserved rather than masked.

### 3.5 The ten analysis notebooks

The analysis notebooks are generated from one module of cells each (`tools/analysis_cells/nb01.py` to `nb10.py`) by `tools/build_analysis_notebooks.py`, which parses every code cell before writing. All ten run end to end on the 2023-24 data in under 70 seconds in total. Every interpretive sentence in them was checked against the executed output, and six were rewritten because the numbers contradicted the first draft.

| Notebook | Methods | Result on the 2023-24 data |
|---|---|---|
| `01_ingest_clean_deidentify` | Analytic join, validation, linkage attack, complementary suppression, public layer | 5,988 institutions in the universe. State + sector + exact headcount re-identifies 93.3% of institutions; region + sector + size band, 1.2%. Primary-only suppression leaves 40 of 279 Colorado groups recoverable, complementary suppression none |
| `02_distributions_and_missingness` | Log transforms, robust outliers, Poisson vs negative binomial, structural missingness | Net tuition skewness 8.85 raw vs 0.06 in logs. Poisson dispersion 159.5; the size elasticity falls from 0.91 to 0.77 under the negative binomial |
| `03_classical_inference` | Welch, Kruskal-Wallis, Cliff's delta with Holm, permutation test, student vs institution weighting | For-profit vs other controls: delta about -0.33. Nonprofit vs public: delta 0.07 (Holm p = 0.011) but permutation p = 0.20 on means. Student weighting raises public and nonprofit means by 7-8 points and lowers for-profit by 2.6 |
| `04_bayesian_shrinkage` | Funnel plot, beta-binomial MLE by control, posterior intervals, out-of-cohort validation | 65% of institutions fall outside 99.8% binomial limits. Priors are worth about 5 students. The raw top 10 has a median cohort of 1, the shrunk top 10 1,634. Predicting the 2017 cohort's rate, shrinkage cuts RMSE by 15.5% for cohorts under 25 and 12% overall |
| `05_clustering_peer_groups` | k-means and GMM model selection, bootstrap ARI, external validation, structural-missingness sensitivity | k = 8 (silhouette about 0.14). Bootstrap ARI median 0.90, k-means vs GMM 0.39, vs Carnegie 0.11. Adding the library block moves the partition to ARI 0.67 |
| `06_pca_institutional_landscape` | Horn's parallel analysis, bootstrap loadings with sign alignment, congruence | 3 components (62% of variance); PC4 passes the eigenvalue-1 rule but not parallel analysis. PC1, a resource axis, correlates 0.59 with bachelor's completion; PC2, scale, about zero |
| `07_regression_enrollment_finance` | OLS with HC3, VIF, residual diagnostics, 5-fold CV against ridge, lasso, and boosting, test-optional missingness | R-squared 0.91; enrollment elasticity 1.04, price elasticity 0.75. Boosting improves RMSE by under 2%. 43% of institutions report no SAT, and adding SAT changes RMSE by 0.001 among reporters |
| `08_classification_completion_risk` | Within-sector target, logistic and boosting, calibration, Pell-tercile error audit, ablation | Institution-level only. AUC 0.76 logistic, 0.81 boosting. Dropping the grant features lowers AUC to 0.77, leaves the high-Pell false-negative rate near 50%, and miscalibrates that group (0.44 predicted vs 0.35 observed) |
| `09_longitudinal_panel_models` | Six-vintage stacking with period assertions, balanced vs unbalanced, two-way FE event study, clustered SEs | Fall-2020 cohort: -2.0 points at public 4-years, recovered by fall 2022. Public 2-years dip a year earlier and end 2.1 points above baseline. Nonprofits are flat. For-profit 4-years are down about 5 points with wide intervals |
| `10_benchmarking_scorecards` | Within-peer robust z, winsorising, a 4-of-6 coverage rule, 500 Dirichlet weightings, a focal scorecard | The median 90% rank interval spans 100 of 207 places. The CU Denver/Anschutz scorecard shows how a resource-based peer model pairs a medical campus with residential flagships |

### 3.6 Further corrections from the analysis layer

Running the analysis notebooks surfaced errors in the shared package that the component notebooks had not exposed:

- **Decoded labels were silently empty.** Reserved-code masking promoted integer code columns to float, so `1` became `1.0` and matched nothing in the dictionary. Every `c01` label column was NaN, and the notebook only printed a warning. `iu.code_key()` now canonicalises float-like codes without touching CIP codes, and decoding asserts that no code is unresolved.
- **Finance totals came from parent/child summary lines.** Lines such as `F3B01` are blank when a parent reports for its children, per the [IPEDS 2022-23 Finance form](https://nces.ed.gov/ipeds/use-the-data/download-survey-material/2022/finance/package_5_12.pdf). They were blank for 1,592 of 2,090 for-profit filers. The analytic table now uses `F1B27`/`F1C191`, `F2D16`/`F2E131`, and `F3D09`/`F3E071`, matching the guidebook crosswalk, and tuition-share coverage rose from 3,498 to 5,697.
- **Library values attributed from a parent.** 273 `DRVAL2023` institutions have no `AL2023` report, and each exactly repeats a reporting institution's profile. They are now flagged and blanked.
- **Two de-identification functions passed silently.** `k_anonymity` ignored absent quasi-identifiers and `suppress` ignored absent columns. Both now raise, and `suppress` reports groups whose only cell is the total, where no complement exists.
- **A missing dependency.** `stats.py` imports SciPy, which the package metadata did not declare.

---

## Sources

All variable names, labels, record grains, reporting thresholds, and reference periods in this specification were confirmed against the official IPEDS Data Center data files and their accompanying dictionaries, retrieved from `https://nces.ed.gov/ipeds/datacenter/data/{TABLE}.zip` and `{TABLE}_Dict.zip`, and cross-checked against each dictionary's Introduction sheet. Component and survey definitions follow the [NCES IPEDS survey components documentation](https://nces.ed.gov/ipeds/survey-components) and the [IPEDS Data Collection System overview](https://www.csn.edu/sites/default/files/pdf_file/0034/158893/IPEDS-Data-Collection-System.pdf). Cautions on cross-standard finance comparability follow the [Delta Cost Project data dictionary](https://nces.ed.gov/ipeds/deltacostproject/download/Delta_Data_Dictionary_1987_2012.xls). Suppression practice for small-cell demographic tables follows the precedent in the [1998 IPEDS Academic Library Survey confidentiality notes](https://nces.ed.gov/pubs2002/2002320.PDF). Pedagogical structure follows [Statistics, Data Mining, and Machine Learning in Astronomy](https://press.princeton.edu/books/hardcover/9780691198309/statistics-data-mining-and-machine-learning-in-astronomy).
