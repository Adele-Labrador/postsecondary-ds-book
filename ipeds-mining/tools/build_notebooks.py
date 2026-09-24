"""Generate the twelve component curation notebooks from a single spec table.

The notebooks are generated rather than hand-written so that the twelve share one
cell skeleton by construction. Editing the skeleton here updates all twelve, which is
what keeps them consistent as the guidebook evolves.

Run:  python tools/build_notebooks.py
"""

from __future__ import annotations

import json
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"

# --- Component specifications ---------------------------------------------------
# period_regex is asserted against the dictionary Introduction sheet, which is the
# authoritative statement of what period a file covers. Filename year is not it.

RESHAPE_F = """
# Finance is the one component that cannot be a pass-through. Three mutually
# incompatible forms cover the sector and must be harmonised onto shared concepts
# before anything can be compared across it:
#
#   F1A -> GASB public institutions
#   F2  -> FASB private not-for-profit (plus a few FASB-reporting publics)
#   F3  -> FASB private for-profit
#
# Every source column below was confirmed against the three FY2023 dictionaries.
#
# Totals come from the revenue and expense detail parts, not the summary parts. For
# FASB filers the summary totals (F2B01/F3B01, "Total revenues and investment return")
# sit in Parts A-B, which a parent institution reports for itself plus ALL its child
# campuses, while children leave them blank. In FY2023 that blanks F3B01 for 1,592 of
# 2,090 for-profit filers, and for parents it puts a system-wide denominator under a
# campus-level tuition numerator. F1D01/F1D02 (GASB Part D) show the same gap: 429 of
# 1,916 blank. The detail totals below are complete for every filer.
# Re-confirm them against cell 4 before reusing this map for another cycle: the forms
# are revised independently of one another, so a column that moved on one form will
# silently mismatch the others.

CONCEPTS = {
    "F1A": {
        "TOTAL_REVENUES": "F1B27",       # Total operating and nonoperating revenues (Part B)
        "TOTAL_EXPENSES": "F1C191",      # Total expenses and deductions, current year (Part C)
        "TUITION_REVENUE": "F1B01",      # Tuition and fees, net of discounts
        "INSTRUCTION_EXPENSE": "F1C011", # Instruction, current year total
        "ENDOWMENT_EOY": "F1H02",        # Endowment assets, end of fiscal year
    },
    "F2": {
        "TOTAL_REVENUES": "F2D16",       # Total revenues and investment return (Part D)
        "TOTAL_EXPENSES": "F2E131",      # Total expenses, total amount (Part E)
        "TUITION_REVENUE": "F2D01",
        "INSTRUCTION_EXPENSE": "F2E011",
        "ENDOWMENT_EOY": "F2H02",
    },
    "F3": {
        "TOTAL_REVENUES": "F3D09",       # Total revenues and investment return (Part D)
        "TOTAL_EXPENSES": "F3E071",      # Total expenses, total amount (Part E)
        "TUITION_REVENUE": "F3D01",
        "INSTRUCTION_EXPENSE": "F3E011",
        "ENDOWMENT_EOY": None,  # For-profit institutions report no endowment.
    },
}

harmonised = []
for form, table in (("F1A", "F2223_F1A"), ("F2", "F2223_F2"), ("F3", "F2223_F3")):
    record = next(r for r in provenance if r["table"] == table)
    part = iu.read_csv(record["data_path"])

    out = pd.DataFrame({"UNITID": part["UNITID"]})
    out["REPORTING_STANDARD"] = form
    for concept, column in CONCEPTS[form].items():
        if column is None:
            out[concept] = np.nan          # structurally absent, not missing data
        elif column in part.columns:
            values = pd.to_numeric(part[column], errors="coerce")
            out[concept] = values.mask(values.isin(RESERVED))
        else:
            out[concept] = np.nan
            print(f"  {form}: source column {column} for {concept} absent this cycle")
    harmonised.append(out)
    print(f"{form:4s} {table:12s} {len(part):5,d} institutions")

curated = pd.concat(harmonised, ignore_index=True)

# An institution must appear on exactly one form. Overlap is a routing error, and it
# would double-count that institution in every sector aggregate downstream.
overlap = curated.UNITID[curated.UNITID.duplicated()].unique()
print()
print(f"{len(curated):,} rows, {len(overlap)} institutions on more than one form")
if len(overlap):
    display(curated[curated.UNITID.isin(overlap)].sort_values("UNITID").head(10))
    curated = curated.drop_duplicates(subset=["UNITID"], keep="first")

print()
print("Share non-null by reporting standard:")
display(
    curated.groupby("REPORTING_STANDARD")[list(CONCEPTS["F1A"].keys())]
    .apply(lambda g: g.notna().mean().round(3))
)
print(
    "ENDOWMENT_EOY is empty for F3 by construction: for-profit institutions do not "
    "report endowment assets. That is a structural absence, not missing data, and it "
    "must not be imputed."
)
"""

COMPONENTS = [
    {
        "slug": "c01_ic",
        "title": "Institutional Characteristics and the Directory Universe",
        "tables": ["HD2023", "IC2023", "IC2023_AY", "DRVIC2023"],
        "period": "2023-24 institutional universe; AY 2023-24 published charges",
        "period_regex": r"2023-24",
        "grain": ["UNITID"],
        "keep": [
            "UNITID",
            "INSTNM",
            "STABBR",
            "FIPS",
            "OBEREG",
            "SECTOR",
            "ICLEVEL",
            "CONTROL",
            "HLOFFER",
            "UGOFFER",
            "GROFFER",
            "HBCU",
            "TRIBAL",
            "LOCALE",
            "C21BASIC",
            "CYACTIVE",
            "INSTCAT",
        ],
        "categoricals": ["CONTROL", "SECTOR", "ICLEVEL", "LOCALE", "C21BASIC"],
        "rules": [
            "iu.unique_key('UNITID')",
            "iu.not_null('UNITID', 'INSTNM')",
            "iu.subset_of('CONTROL', {1, 2, 3, -3})",
            "iu.in_range('SECTOR', 0, 99)",
        ],
        "notes": (
            "This notebook produces the peer-group spine every other component joins "
            "against. Filter to `CYACTIVE == 1` for analyses that require a currently "
            "active institution, but keep inactive rows in the curated table so that "
            "closures remain visible to the longitudinal notebooks rather than silently "
            "vanishing from a panel."
        ),
        "pitfall": (
            "Negative values are not data. IPEDS uses -1, -2, and -3 as reserved missing "
            "codes; a mean computed without masking them is badly wrong and looks fine."
        ),
    },
    {
        "slug": "c02_adm",
        "title": "Admissions and Test Scores",
        "tables": ["ADM2023"],
        "period": "Fall 2023 cohort of first-time degree-seeking undergraduates",
        "period_regex": r"(fall 2023|2023-24)",
        "grain": ["UNITID"],
        "keep": [
            "UNITID",
            "APPLCN",
            "APPLCNM",
            "APPLCNW",
            "ADMSSN",
            "ADMSSNM",
            "ADMSSNW",
            "ENRLT",
            "ENRLM",
            "ENRLW",
            "SATNUM",
            "SATPCT",
            "ACTNUM",
            "ACTPCT",
            "SATVR25",
            "SATVR75",
            "SATMT25",
            "SATMT75",
            "ACTCM25",
            "ACTCM75",
            "ADMCON1",
            "ADMCON2",
        ],
        "categoricals": ["ADMCON1", "ADMCON2"],
        "rules": [
            "iu.unique_key('UNITID')",
            "iu.in_range('APPLCN', 0, None)",
            "iu.Rule('admitted_le_applied', lambda d: pd.to_numeric(d.ADMSSN, errors='coerce') > pd.to_numeric(d.APPLCN, errors='coerce'), note='Admits cannot exceed applicants')",
            "iu.Rule('enrolled_le_admitted', lambda d: pd.to_numeric(d.ENRLT, errors='coerce') > pd.to_numeric(d.ADMSSN, errors='coerce'), note='Enrolled cannot exceed admits')",
        ],
        "notes": (
            "The funnel identity applications >= admissions >= enrolled is a free integrity "
            "check that catches transcription errors and mis-joined years immediately."
        ),
        "pitfall": (
            "Score percentiles are conditional on the submitting subgroup, whose size is "
            "`SATPCT`/`ACTPCT`. In a test-optional era those percentages fall sharply and "
            "the reported percentiles rise, which is a composition change and not an "
            "improvement in selectivity. Never model a score band without carrying its "
            "submission share alongside it."
        ),
    },
    {
        "slug": "c03_e12",
        "title": "Twelve-Month Enrollment and Instructional Activity",
        "tables": ["EFFY2023", "EFIA2023", "DRVEF122023"],
        "period": "July 1, 2022 through June 30, 2023",
        "period_regex": r"(July 1, 2022|2022-23)",
        "grain": ["UNITID", "EFFYALEV"],
        "keep": [
            "UNITID",
            "EFFYALEV",
            "EFFYLEV",
            "LSTUDY",
            "EFYTOTLT",
            "EFYTOTLM",
            "EFYTOTLW",
            "EFYGUKN",
            "EFYGUAN",
            "EFYAIANT",
            "EFYASIAT",
            "EFYBKAAT",
            "EFYHISPT",
            "EFYNHPIT",
            "EFYWHITT",
            "EFY2MORT",
            "EFYUNKNT",
            "EFYNRALT",
        ],
        "categoricals": ["EFFYLEV"],
        "rules": [
            "iu.unique_key('UNITID', 'EFFYALEV')",
            "iu.in_range('EFYTOTLT', 0, None)",
            "iu.sums_to('EFYTOTLT', ['EFYAIANT','EFYASIAT','EFYBKAAT','EFYHISPT','EFYNHPIT','EFYWHITT','EFY2MORT','EFYUNKNT','EFYNRALT'], severity='warn')",
        ],
        "notes": (
            "Twelve-month unduplicated headcount is the right denominator for cost-per-student "
            "measures because it matches the fiscal year that Finance reports on. Fall census "
            "counts do not, and mixing the two understates cost per student at institutions "
            "with heavy summer enrollment.\n\nThe grain is `UNITID` x `EFFYALEV`, which carries "
            "27 distinct level codes. `EFFYLEV` (4 codes) and `LSTUDY` (3 codes) are coarser "
            "rollups of the same records, so the file contains totals alongside their own "
            "components. Select the level rows you need; never sum across them."
        ),
        "pitfall": (
            "Do not assume EFYTOTLM + EFYTOTLW == EFYTOTLT. Gender-inclusive reporting "
            "categories mean the men/women columns no longer partition the total. Any "
            "men/women share must use EFYGUKN as its denominator, or shares will quietly "
            "sum to under 100 percent at exactly the institutions using the newer categories."
        ),
    },
    {
        "slug": "c04_ef",
        "title": "Fall Enrollment, Retention, and Student-to-Faculty Ratio",
        "tables": ["EF2023A", "EF2023B", "EF2023C", "EF2023D", "DRVEF2023"],
        "period": "Fall 2023 census date",
        "period_regex": r"(fall 2023|2023-24)",
        "grain": ["UNITID", "EFALEVEL"],
        "keep": ["UNITID", "EFALEVEL", "EFTOTLT", "EFTOTLM", "EFTOTLW"],
        "categoricals": ["EFALEVEL"],
        "rules": [
            "iu.unique_key('UNITID', 'EFALEVEL')",
            "iu.in_range('EFTOTLT', 0, None)",
        ],
        "notes": (
            "Retention and student-to-faculty ratio live in EF2023D, at UNITID grain, and are "
            "the two most reused features in the modelling chapters. EF2023A is level by "
            "demographic detail; select the EFALEVEL rows you need rather than summing "
            "across them, because the file mixes totals with their own components."
        ),
        "pitfall": (
            "EF2023D reports RET_PCF for full-time and RET_PCP for part-time cohorts. They are "
            "different denominators and are not interchangeable; most published 'retention "
            "rate' figures mean RET_PCF, and silently substituting the part-time series "
            "produces a different and much noisier measure."
        ),
    },
    {
        "slug": "c05_c",
        "title": "Completions by Program, Level, and Demographic Group",
        "tables": ["C2023_A", "C2023_B", "C2023_C", "DRVC2023"],
        "period": "Awards conferred July 1, 2022 through June 30, 2023",
        "period_regex": r"(July 1, 2022|2022-23)",
        "grain": ["UNITID", "CIPCODE", "AWLEVEL", "MAJORNUM"],
        "keep": ["UNITID", "CIPCODE", "MAJORNUM", "AWLEVEL", "CTOTALT", "CTOTALM", "CTOTALW"],
        "categoricals": ["AWLEVEL"],
        "rules": [
            "iu.unique_key('UNITID', 'CIPCODE', 'AWLEVEL', 'MAJORNUM')",
            "iu.in_range('CTOTALT', 0, None)",
            "iu.rolls_up('CTOTALT', level='CIPCODE', total_code='99', keys=['UNITID', 'AWLEVEL', 'MAJORNUM'])",
        ],
        "notes": (
            "C2023_A counts awards, not people, and stores totals beside their detail: each "
            "UNITID x AWLEVEL x MAJORNUM has a CIPCODE == '99' row equal to the sum of its "
            "programme rows. Summing CTOTALT over every row therefore counts each award twice; "
            "the rolls_up rule below checks the identity. Institution award totals come from the "
            "CIPCODE '99' rows with MAJORNUM == 1, since second majors are not additional awards. "
            "CIPCODE is read as text: parsed as a number, 13.0100 becomes 13.01 and 01.0000 "
            "becomes 1.0. Unique completers are a separate file, C2023_C."
        ),
        "pitfall": (
            "The 2020 CIP revision breaks program-level time series. Any completions trend "
            "spanning 2019 to 2020 must be built on a CIP crosswalk, and program-level "
            "changes across that boundary are otherwise taxonomy artefacts rather than real "
            "shifts in what institutions award."
        ),
    },
    {
        "slug": "c06_gr",
        "title": "Graduation Rates at 150 Percent of Normal Time",
        "tables": ["GR2023", "DRVGR2023"],
        "period": (
            "Status as of August 31, 2023 for the 2017 entering cohort at 4-year "
            "institutions and the 2020 entering cohort at 2-year institutions"
        ),
        "period_regex": r"cohort year 2017",
        "grain": ["UNITID", "GRTYPE"],
        "keep": [
            "UNITID",
            "GRTYPE",
            "CHRTSTAT",
            "SECTION",
            "COHORT",
            "GRTOTLT",
            "GRTOTLM",
            "GRTOTLW",
        ],
        "categoricals": ["GRTYPE", "CHRTSTAT"],
        "rules": [
            "iu.unique_key('UNITID', 'GRTYPE')",
            "iu.in_range('GRTOTLT', 0, None)",
        ],
        "notes": (
            "The cohort year differs by institution level within this one file: 2017 entering "
            "for 4-year institutions, 2020 entering for 2-year institutions, both measured as "
            "of August 31, 2023. A panel that treats GR2023 as a single cohort year is wrong "
            "for one of the two sectors."
        ),
        "pitfall": (
            "GRTYPE encodes cohort mechanics, not demographics: the revised cohort, exclusions, "
            "the adjusted cohort, completers, and transfer-outs are separate rows. Compute "
            "rates as completers over adjusted cohort and retain numerator and denominator as "
            "separate columns, so the beta-binomial model in Notebook 04 remains possible. A "
            "pre-divided rate throws away the sample size that model needs."
        ),
    },
    {
        "slug": "c07_gr200",
        "title": "Graduation Rates at 200 Percent of Normal Time",
        "tables": ["GR200_23"],
        "period": (
            "Status as of August 31, 2023 for the 2015 entering cohort at 4-year "
            "institutions and the 2019 entering cohort at less-than-4-year institutions"
        ),
        "period_regex": r"cohort year 2015",
        "grain": ["UNITID"],
        "keep": ["UNITID", "BAGR100", "BAGR150", "BAGR200", "L4GR100", "L4GR150", "L4GR200"],
        "categoricals": [],
        "rules": [
            "iu.unique_key('UNITID')",
            "iu.in_range('BAGR200', 0, 100, severity='warn')",
            "iu.Rule('monotone_200_ge_150', lambda d: pd.to_numeric(d.BAGR200, errors='coerce') < pd.to_numeric(d.BAGR150, errors='coerce'), note='200% rate cannot fall below the 150% rate')",
        ],
        "notes": (
            "The extended window answers a different question from the 150 percent rate: how "
            "many students finish eventually. The gap between BAGR150 and BAGR200 is itself "
            "the interesting feature, because it separates institutions serving students who "
            "complete slowly from those whose students do not complete at all."
        ),
        "pitfall": (
            "These are already percentages, not counts, so they cannot be aggregated across "
            "institutions by averaging without weighting by cohort size. The monotonicity "
            "check is the cheapest available test that a join has not gone wrong."
        ),
    },
    {
        "slug": "c08_om",
        "title": "Outcome Measures for Non-Traditional Cohorts",
        "tables": ["OM2023", "DRVOM2023"],
        "period": (
            "2015-16 entering cohort observed at 4, 6, and 8 years "
            "(August 31 2019, 2021, and 2023)"
        ),
        "period_regex": r"2015-16",
        "grain": ["UNITID", "OMCHRT"],
        "keep": [
            "UNITID",
            "OMCHRT",
            "OMRCHRT",
            "OMACHRT",
            "OMAWDN4",
            "OMAWDN6",
            "OMAWDN8",
            "OMAWDP8",
            "OMENRYI",
            "OMENRAI",
            "OMENRUN",
            "OMNOAWD",
            "OMENRUP",
            "OMENRTP",
        ],
        "categoricals": ["OMCHRT"],
        "rules": [
            "iu.unique_key('UNITID', 'OMCHRT')",
            "iu.in_range('OMACHRT', 0, None)",
            "iu.Rule('adjusted_le_reported', lambda d: pd.to_numeric(d.OMACHRT, errors='coerce') > pd.to_numeric(d.OMRCHRT, errors='coerce'), note='Adjusted cohort cannot exceed the reported cohort')",
            "iu.sums_to('OMACHRT', ['OMAWDN8', 'OMENRYI', 'OMENRAI', 'OMENRUN'], severity='warn')",
            "iu.Rule('award_monotone_4_6_8', lambda d: (pd.to_numeric(d.OMAWDN8, errors='coerce') < pd.to_numeric(d.OMAWDN6, errors='coerce')) | (pd.to_numeric(d.OMAWDN6, errors='coerce') < pd.to_numeric(d.OMAWDN4, errors='coerce')), note='Cumulative awards cannot decrease as the window widens')",
        ],
        "notes": (
            "Outcome Measures exists because the Graduation Rates cohort excludes part-time "
            "and non-first-time students, which at open-access and community institutions is "
            "most of the student body. OMCHRT splits the cohort by entry status, and those "
            "splits are the point of the component rather than a nuisance dimension."
        ),
        "pitfall": (
            "OMENRUN is measured ignorance, not zero. It counts students whose subsequent "
            "enrollment status could not be determined. Treating it as a non-completion "
            "inflates apparent failure at institutions with poor match rates to the National "
            "Student Clearinghouse. Carry OMENRUP as an explicit uncertainty band: the honest "
            "completion estimate is an interval whose width is that unknown share, not a point."
        ),
    },
    {
        "slug": "c09_sfa",
        "title": "Student Financial Aid and Net Price",
        "tables": ["SFA2223", "SFAV2223"],
        "period": "2022-23 aid year",
        "period_regex": r"2022-23",
        "grain": ["UNITID"],
        "keep": [
            "UNITID",
            "SCUGRAD",
            "SCUGFFN",
            "ANYAIDN",
            "ANYAIDP",
            "FGRNT_N",
            "FGRNT_P",
            "FGRNT_A",
            "PGRNT_N",
            "PGRNT_P",
            "PGRNT_A",
            "FLOAN_N",
            "FLOAN_P",
            "FLOAN_A",
            "NPIST2",
            "NPT412",
            "GIS4N12",
        ],
        "categoricals": [],
        "rules": [
            "iu.unique_key('UNITID')",
            "iu.in_range('ANYAIDP', 0, 100, severity='warn')",
            "iu.Rule('pell_le_federal_grant', lambda d: pd.to_numeric(d.PGRNT_N, errors='coerce') > pd.to_numeric(d.FGRNT_N, errors='coerce'), note='Pell recipients are a subset of federal grant recipients')",
        ],
        "notes": (
            "The N/P/A triple is a built-in consistency check: the count of recipients, the "
            "percentage of the relevant cohort, and the average award. Recomputing the "
            "percentage from the count and the denominator should reproduce the published "
            "figure, and a mismatch means the wrong denominator was used."
        ),
        "pitfall": (
            "Denominators differ within the same file. Some measures apply to full-time "
            "first-time degree-seeking undergraduates (SCUGFFN) and others to all "
            "undergraduates (SCUGRAD). Net price series are further restricted to students "
            "receiving Title IV aid, so a net-price comparison across institutions with very "
            "different aid participation is not comparing the same population."
        ),
    },
    {
        "slug": "c10_f",
        "title": "Finance Under Three Accounting Standards",
        "tables": ["F2223_F1A", "F2223_F2", "F2223_F3", "DRVF2023"],
        "period": "Fiscal year 2023",
        "period_regex": r"(2022-23|fiscal year 2023|FY2023)",
        "grain": ["UNITID"],
        "keep": ["UNITID"],
        "categoricals": [],
        "rules": [
            "iu.unique_key('UNITID')",
            "iu.not_null('REPORTING_STANDARD')",
            "iu.in_range('TOTAL_REVENUES', 0, None, severity='warn')",
            "iu.in_range('TOTAL_EXPENSES', 0, None, severity='warn')",
        ],
        "reshape": RESHAPE_F,
        "notes": (
            "Three mutually incompatible forms cover the sector: F1A for GASB public "
            "institutions, F2 for FASB private not-for-profit institutions and a small number "
            "of FASB-reporting publics, and F3 for private for-profit institutions. Route "
            "each UNITID by CONTROL from the c01 spine, harmonise onto common concepts, and "
            "keep a reporting_standard column on every row so no downstream comparison can "
            "silently cross the standards."
        ),
        "pitfall": (
            "The same economic concept has different variable names and sometimes different "
            "definitions on each form. Comparing a GASB expense total directly against a FASB "
            "one is the single most common serious error in IPEDS finance work. Prefer the "
            "derived file DRVF2023 for cross-sector comparison, because NCES has already done "
            "the harmonisation there, and use the raw forms when a specific line item is "
            "needed that the derived file does not carry."
        ),
    },
    {
        "slug": "c11_hr",
        "title": "Human Resources, Staffing Mix, and Tenure",
        "tables": ["S2023_OC", "S2023_IS", "S2023_SIS", "S2023_NH", "SAL2023_IS", "DRVHR2023"],
        "period": "Payroll snapshot of November 1, 2023; salary outlays for AY 2023-24",
        "period_regex": r"(Fall 2023|November 1)",
        "grain": ["UNITID", "STAFFCAT"],
        "keep": [
            "UNITID",
            "STAFFCAT",
            "FTPT",
            "OCCUPCAT",
            "SABDTYPE",
            "HRTOTLT",
            "HRTOTLM",
            "HRTOTLW",
        ],
        "categoricals": ["STAFFCAT", "FTPT", "OCCUPCAT"],
        "rules": [
            "iu.unique_key('UNITID', 'STAFFCAT')",
            "iu.in_range('HRTOTLT', 0, None)",
        ],
        "notes": (
            "Use S2023_OC for the standing stock of employees by occupational category and "
            "S2023_SIS for tenure status by FACSTAT. These are snapshots of who is employed. "
            "Note that STAFFCAT bundles occupation with full- and part-time status, while "
            "OCCUPCAT and FTPT carry those two dimensions separately; prefer the separated "
            "columns when building features, and use SABDTYPE only when you need continuity "
            "with the pre-2012 occupational coding."
        ),
        "pitfall": (
            "S2023_NH is a flow, not a stock: it counts people hired between November 1, 2022 "
            "and October 31, 2023. Using it for staffing mix or tenure density measures the "
            "composition of one year's hiring rather than the composition of the workforce, "
            "and the two differ most at exactly the institutions undergoing change. Note also "
            "that STAFFCAT includes nested aggregate codes; summing across all of them "
            "double-counts."
        ),
    },
    {
        "slug": "c12_al",
        "title": "Academic Libraries",
        "tables": ["AL2023", "DRVAL2023"],
        "period": "Fiscal year 2023",
        "period_regex": r"(2022-23|fiscal year 2023|FY2023)",
        "grain": ["UNITID"],
        "keep": [
            "UNITID",
            "LEXP100K",
            "LCOLELYN",
            "LEXPTOT",
            "LSALWAG",
            "LFRNGBYN",
            "LFRNGBN",
            "LEXMSTL",
            "LEXMSBB",
            "LEXMSCS",
            "LEXMSOT",
            "LEXOMTL",
            "LEXOMPS",
            "LEXOMOT",
            "LSTOTAL",
            "LSLIBRN",
            "LPBOOKS",
            "LEBOOKS",
            "LEDATAB",
            "LTCLLCT",
            "LTCRCLT",
        ],
        "categoricals": ["LEXP100K", "LCOLELYN"],
        "rules": [
            "iu.unique_key('UNITID')",
            "iu.in_range('LEXPTOT', 0, None)",
            "iu.sums_to('LEXPTOT', ['LSALWAG', 'LFRNGBN', 'LEXMSTL', 'LEXOMTL'], tolerance=1)",
            "iu.sums_to('LEXMSTL', ['LEXMSBB', 'LEXMSCS', 'LEXMSOT'], tolerance=1)",
            "iu.sums_to('LEXOMTL', ['LEXOMPS', 'LEXOMOT'], tolerance=1)",
        ],
        "notes": (
            "Library expenditure per student is a useful proxy for instructional support "
            "intensity, and it pairs naturally with the twelve-month enrollment denominator "
            "from c03 rather than a fall census count, because both are fiscal-year figures."
            "\n\nThe expenditure hierarchy reconciles exactly, and the three `sums_to` rules "
            "below are therefore error-level rather than warnings: `LEXPTOT` is the sum of "
            "salaries and wages, **fringe benefits**, materials and services, and operations "
            "and maintenance. Omitting `LFRNGBN` is an easy mistake that breaks reconciliation "
            "for roughly two thirds of reporting institutions while leaving the other third "
            "apparently fine, which is exactly the kind of partial failure a hard rule catches "
            "and a spot check does not."
        ),
        "pitfall": (
            "The component is screener-gated, and the screener is visible in the data: "
            "LEXP100K records whether total library expenses reached $100,000, and "
            "institutions below that threshold skip the detailed expenditure items. A null in "
            "LEXMSTL therefore usually means not asked rather than zero. Imputing zeros would "
            "fabricate a large population of libraryless institutions that does not exist. "
            "Condition on LEXP100K before interpreting any detail item."
        ),
    },
]

# --- Cell skeleton --------------------------------------------------------------


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


def build(spec: dict) -> nbf.NotebookNode:
    slug, title = spec["slug"], spec["title"]
    tables = spec["tables"]
    grain = spec["grain"]
    keep = spec["keep"]
    rules = spec["rules"]

    cells = [
        md(f"""
# `{slug}` — {title}

**Component curation notebook.** Fetches the raw IPEDS distribution files, verifies the
reference period against official documentation, locks the schema, reshapes to the
declared grain, validates, and writes one curated table with a metadata sidecar.

| Property | Value |
|---|---|
| Native tables | {', '.join(f'`{t}`' for t in tables)} |
| Reference period | {spec['period']} |
| Curated grain | {' x '.join(f'`{g}`' for g in grain)} |
| Output | `data/curated/{slug}.parquet` |

{spec['notes']}

> **Pitfall.** {spec['pitfall']}
"""),
        md(
            "## 1. Environment\n\nOne import surface, so a parsing quirk is fixed once rather than twelve times."
        ),
        code(f"""
import sys, warnings
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parent / "src"))

import numpy as np
import pandas as pd
import ipeds_utils as iu

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 60)
warnings.filterwarnings("ignore", category=FutureWarning)

SLUG = "{slug}"
TABLES = {tables!r}
GRAIN = {grain!r}
REFERENCE_PERIOD = {spec['period']!r}

print("ipeds_utils", iu.__version__, "| pandas", pd.__version__)
"""),
        md(
            "## 2. Retrieve\n\nDownloads are cached, so re-running this notebook is offline and "
            "cheap. Every retrieval returns a provenance record carrying a SHA-256 digest, which "
            "is what makes a result reproducible rather than merely repeatable."
        ),
        code("""
RAW_DIR = "../data/raw"   # relative to notebooks/, so all twelve share one cache

provenance = [iu.fetch(t, raw_dir=RAW_DIR) for t in TABLES]
pd.DataFrame(provenance)[["table", "data_bytes", "data_sha256", "retrieved_utc"]]
"""),
        md(
            "## 3. Verify the reference period\n\n**Do not skip this cell.** The filename year is "
            "not the reference period, and the offsets are not uniform across components. This "
            "assertion fails loudly rather than letting a misaligned period corrupt every "
            "downstream year comparison, where it would be invisible in the data itself."
        ),
        code(f"""
intro = iu.assert_reference_period(
    provenance[0]["dict_path"],
    expect=r{spec['period_regex']!r},
    table=TABLES[0],
)
print(intro[:600])
"""),
        md(
            "## 4. Inspect the dictionary\n\nVariable labels come from the published dictionary, "
            "never from memory. This is also where value sets are read, so categorical decoding "
            "is driven by the official codebook and a taxonomy revision surfaces as unmatched "
            "codes instead of a plausible-looking wrong label."
        ),
        code("""
variables = iu.read_dict(provenance[0]["dict_path"])
valuesets = iu.read_valuesets(provenance[0]["dict_path"])

print(f"{len(variables)} variables documented, {len(valuesets)} value-set rows")
variables[["varname", "vartitle"]].head(20)
"""),
        md(
            "## 5. Load and lock the schema\n\nThe first run records the column signature; later runs fail if it drifts."
        ),
        code(f"""
KEEP = {keep!r}

raw = iu.read_csv(provenance[0]["data_path"])
print("raw shape", raw.shape)

lock = iu.lock_schema(raw, TABLES[0], schema_dir="../schemas", strict=False)
print("schema:", lock["status"], "| added", lock["added"][:5], "| removed", lock["removed"][:5])

available = [c for c in KEEP if c in raw.columns]
missing = [c for c in KEEP if c not in raw.columns]
if missing:
    print("NOT PRESENT in this cycle (verify against the varlist above):", missing)

frame = raw[available].copy()
frame.head()
"""),
        md(
            "## 6. Mask reserved missing codes\n\nIPEDS encodes missingness as negative integers. "
            "A mean computed without masking them is badly wrong and looks entirely plausible, "
            "which is what makes this the most costly single omission in IPEDS analysis."
        ),
        code(f"""
RESERVED = [-1, -2, -3, -9]

numeric_cols = [
    c for c in frame.columns
    if c not in ("UNITID", *GRAIN) and pd.api.types.is_numeric_dtype(frame[c])
]

before = frame[numeric_cols].isna().sum().sum()
for col in numeric_cols:
    frame.loc[frame[col].isin(RESERVED), col] = np.nan
after = frame[numeric_cols].isna().sum().sum()

# Masking turns an integer column into float (1 becomes 1.0). Measures can stay float,
# since NaN is what the models expect, but category codes go back to nullable integers
# so they print, join, and decode as codes rather than as 1.0.
for col in {spec['categoricals']!r}:
    if col in frame.columns and pd.api.types.is_float_dtype(frame[col]):
        if (frame[col].dropna() % 1 == 0).all():
            frame[col] = frame[col].astype("Int64")

print(f"masked {{after - before:,}} reserved-code cells across {{len(numeric_cols)}} numeric columns")
"""),
        md(
            "## 7. Carry the imputation flags\n\nAn imputed value and a reported value are not the "
            "same evidence. A column where most institutions carry a generated flag should not be "
            "modelled as though it were observed, and this is where that judgement becomes possible."
        ),
        code("""
values, flags = iu.split_imputation_flags(raw, numeric_cols)

if flags.shape[1] > 1:
    summary = iu.imputation_summary(flags)
    display(summary.head(15))
    reported = summary[summary.flag == "R"].set_index("column")["share"]
    weak = reported[reported < 0.90]
    if len(weak):
        print("Columns under 90% reported — interpret with care:")
        display(weak)
else:
    print("No X-prefixed imputation flags accompany this file.")
"""),
        md(
            "## 8. Decode categoricals\n\nLabels from the published value sets, not hand-typed mappings."
        ),
        code(f"""
CATEGORICALS = {spec['categoricals']!r}

unresolved = {{}}
for col in CATEGORICALS:
    if col in frame.columns:
        frame = iu.decode(frame, valuesets, col)
        unmatched = frame.loc[frame[col].notna() & frame[f"{{col}}_LABEL"].isna(), col].unique()
        if len(unmatched):
            unresolved[col] = sorted(unmatched.tolist())[:10]

# An unmatched code means a taxonomy change or a parsing fault. Either way the
# labels are wrong, so this stops the notebook rather than printing a warning.
assert not unresolved, f"codes absent from the published value set: {{unresolved}}"

label_cols = [c for c in frame.columns if c.endswith("_LABEL")]
frame[CATEGORICALS + label_cols].drop_duplicates().head(20) if label_cols else frame.head()
"""),
        md(
            f"## 9. Reshape to the declared grain\n\nTarget grain: {' x '.join(f'`{g}`' for g in grain)}. "
            "The grain is asserted, not assumed, because a duplicated key silently inflates every "
            "aggregate computed downstream."
        ),
        code("""
curated = frame.copy()

__RESHAPE__

present_grain = [g for g in GRAIN if g in curated.columns]
duplicated = curated.duplicated(subset=present_grain, keep=False).sum()
print(f"grain {present_grain} -> {len(curated):,} rows, {duplicated} duplicated")
assert duplicated == 0, "Declared grain is not unique; resolve before continuing."

curated.head()
"""),
        md(
            "## 10. Validate\n\nRules are declarative so the output is a persistable report: which "
            "checks ran, which failed, on how many rows, and which institutions were implicated. "
            "That report is the artefact you cite when claiming this table is fit for analysis."
        ),
        code(f"""
RULES = [
    {chr(10).join('    ' + r + ',' for r in rules).strip()}
]

report = iu.validate(curated, RULES, SLUG)
report.save(f"../reports/validation/{{SLUG}}.json")
display(report.to_frame()[["name", "status", "n_offending", "share", "note"]])

print("PASSED" if report.ok else "FAILED")
report.raise_if_failed()
"""),
        md(
            "## 11. Write the curated table\n\nThe sidecar carries the reference period and grain "
            "with the data. This is the defence against assembling a panel by filename year when "
            "the underlying periods are offset differently per component."
        ),
        code(f"""
path = iu.write_curated(
    curated,
    SLUG,
    root="../data/curated",
    reference_period=REFERENCE_PERIOD,
    grain=GRAIN,
    provenance=provenance,
    notes={spec['pitfall']!r},
)

iu.write_provenance(provenance, f"../docs/provenance/{{SLUG}}.json")
print("wrote", path, f"({{len(curated):,}} rows x {{curated.shape[1]}} columns)")
"""),
        md(
            "## 12. Exercises\n\n1. Re-run this notebook against the prior collection cycle by "
            "changing `TABLES`. The schema lock and the period assertion will both object; resolve "
            "each objection and record what changed between cycles.\n"
            "2. Identify the three columns with the lowest reported-flag share, and argue whether "
            "each belongs in a predictive model at all.\n"
            "3. Construct one derived cross-tabulation from this table, then apply "
            "`iu.suppress` and `iu.k_anonymity` to it. Report the smallest equivalence class "
            "before and after coarsening, and state the k you would require before publishing.\n"
            f"4. {spec['pitfall'].split('.')[0]}. Write a validation rule that would catch this "
            "error if a colleague made it, and add it to `RULES` above."
        ),
    ]

    default_reshape = (
        "# This component already arrives at its declared grain, so curation is a\n"
        "# pass-through. Components with a long layout (GRTYPE, EFFYALEV, STAFFCAT,\n"
        "# OMCHRT) filter or pivot here instead; see c10_f for a full worked reshape."
    )
    reshape_body = spec.get("reshape", default_reshape).strip()
    for cell in cells:
        if cell.cell_type == "code" and "__RESHAPE__" in cell.source:
            cell.source = cell.source.replace("__RESHAPE__", reshape_body)

    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "ipeds": {
            "slug": slug,
            "tables": tables,
            "reference_period": spec["period"],
            "grain": grain,
        },
    }
    return notebook


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for spec in COMPONENTS:
        notebook = build(spec)
        path = OUT / f"{spec['slug']}.ipynb"
        nbf.write(notebook, path)
        manifest.append(
            {
                "slug": spec["slug"],
                "title": spec["title"],
                "tables": spec["tables"],
                "reference_period": spec["period"],
                "grain": spec["grain"],
                "cells": len(notebook.cells),
                "path": f"notebooks/{spec['slug']}.ipynb",
            }
        )
        print(f"wrote {path.name:24s} {len(notebook.cells):2d} cells")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n{len(manifest)} notebooks + manifest.json")


if __name__ == "__main__":
    main()
