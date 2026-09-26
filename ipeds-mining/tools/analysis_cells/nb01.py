from .common import SETUP, code, md

TITLE = "Ingest, Clean, and De-identify"
FILE = "01_ingest_clean_deidentify.ipynb"

CELLS = [
    md("""
    # 01 — Ingest, Clean, and De-identify

    **Chapter 3 companion.** The twelve component notebooks each curate one survey at its
    native grain. This notebook joins them, with fifteen companion files from the
    Data Center, into one row per institution: the analytic table that notebooks 02–10
    read. It then shows, with real re-identification numbers, why removing names is not
    de-identification.

    | | |
    |---|---|
    | Inputs | `data/curated/c01`–`c12` parquet, plus companion `DRV*` files fetched on demand |
    | Outputs | `data/analytic/institutions_2023.parquet` (identified), `data/public/institutions_2023_public.parquet` (coarsened, pseudonymised), `docs/analytic_dictionary.csv` |
    | Methods | Multi-survey joins with one-to-one validation, reference-period assertion, universe definition, k-anonymity, linkage attack, complementary suppression, keyed pseudonymisation |
    """),
    code(SETUP),
    md("""
    ## 1. Assemble the analytic table

    `iu.institution_table` does three things a hand-written merge usually skips. Every
    join is declared `one_to_one`, so a file that turns out to be long (as `S2023_SIS`
    and `SAL2023_IS` are) fails instead of multiplying rows. Every companion file's
    reference period is asserted against its own Introduction sheet. And every ratio
    returns NaN, never infinity, when its denominator is zero.
    """),
    code(r"""
    inst, provenance = iu.institution_table(curated_root="../data/curated", raw_dir="../data/raw")
    print(f"{len(inst):,} institutions x {inst.shape[1]} columns; UNITID unique: {inst['UNITID'].is_unique}")

    (pd.DataFrame(provenance)[["table", "period_check", "data_sha256"]]
       .assign(data_sha256=lambda d: d["data_sha256"].str[:12]))
    """),
    md("""
    One file cannot be checked. `DRVEF122023` ships with an empty Introduction sheet, so
    its period is recorded as not assertable, with the reason, rather than silently
    assumed. The 12-month window it describes, July 1, 2022 to June 30, 2023, is asserted
    on `EFFY2023` in `c03_e12`.
    """),
    md("""
    ## 2. Define the analysis universe

    The directory file includes administrative system offices (sector 0), which report
    no students, and institutions no longer active in the current year. Leaving them in
    produces rows that are mostly missing, which then look like a data-quality problem
    rather than the scoping decision they are.
    """),
    code(r"""
    inst["IN_UNIVERSE"] = (inst["CYACTIVE"] == 1) & inst["SECTOR"].between(1, 9)

    print(f"in universe: {inst['IN_UNIVERSE'].sum():,}   excluded: {(~inst['IN_UNIVERSE']).sum():,}")
    (inst.loc[~inst["IN_UNIVERSE"]]
         .assign(reason=lambda d: np.where(d["CYACTIVE"] != 1, "inactive this year",
                                           d["SECTOR_LABEL"].fillna("no sector")))
         ["reason"].value_counts().to_frame("institutions"))
    """),
    code(r"""
    universe = inst[inst["IN_UNIVERSE"]]
    universe["SECTOR_LABEL"].value_counts().to_frame("institutions")
    """),
    md("""
    ## 3. Cross-survey consistency checks

    Joining surveys creates checks that no single survey can run. Fall headcount appears
    both in `EF2023A` (curated in `c04_ef`) and in the derived `DRVEF2023`; they should
    agree. Several engineered shares must lie in [0, 1]. Tuition revenue as a share of
    total revenue is set to warn rather than fail, for a reason the next cell shows.
    """),
    code(r"""
    fall_mismatch = iu.Rule(
        "fall_headcount_EF2023A_vs_DRVEF2023",
        lambda d: d["ENROLL_FALL"].notna() & d["ENRTOT"].notna() & (d["ENROLL_FALL"] != d["ENRTOT"]),
        severity="warn",
        note="EF2023A all-student total should equal DRVEF2023 ENRTOT",
    )
    rules = [
        iu.unique_key("UNITID"),
        iu.in_range("RET_PCF", 0, 100),
        iu.in_range("BA_RATE_150", 0, 1),
        iu.in_range("INSTR_FTE_SHARE", 0, 1),
        iu.in_range("TENURE_DENSITY", 0, 1),
        iu.in_range("INSTR_EXP_SHARE", 0, 1),
        iu.in_range("TUITION_SHARE", 0, 1, severity="warn"),
        fall_mismatch,
    ]
    report = iu.validate(universe, rules, "institutions_2023")
    report.save("../reports/validation/institutions_2023.json")
    print("report ok:", report.ok)
    report.to_frame()[["name", "severity", "n_offending", "status", "sample_unitids"]]
    """),
    code(r"""
    over = universe[universe["TUITION_SHARE"] > 1]
    over[["REPORTING_STANDARD", "TUITION_REVENUE", "TOTAL_REVENUES", "TUITION_SHARE"]]
    """),
    md("""
    Every institution with tuition above 100% of total revenue reports under FASB (`F2`
    or `F3`). Total revenue there nets investment returns, so a year of investment
    losses can pull the total below tuition alone. The values are genuine, which is why
    the rule warns rather than fails; `iu.peer_feature_matrix` clips the share to 1 so
    those few institutions don't dominate distance calculations in notebooks 05 and 06.
    """),
    md("""
    ## 4. Document the analytic columns

    Engineered columns get a written source, so a reader of any later notebook can trace
    `TENURE_DENSITY` back to `S2023_SIS` FACSTAT codes without reading this code.
    """),
    code(r"""
    dictionary = pd.DataFrame(
        [{"column": c, "source": s, "non_missing": int(universe[c].notna().sum())}
         for c, s in iu.COLUMN_SOURCES.items()]
    )
    Path("../docs").mkdir(exist_ok=True)
    dictionary.to_csv("../docs/analytic_dictionary.csv", index=False)
    dictionary
    """),
    code(r"""
    inst.to_parquet(ANALYTIC / "institutions_2023.parquet", index=False)
    print("wrote", ANALYTIC / "institutions_2023.parquet", inst.shape)
    """),
    md("""
    ## 5. Why dropping names is not de-identification

    IPEDS institution files are public, so nothing here protects anyone in the raw data.
    What follows matters for derived products and for the moment an institution-level
    file gets linked to restricted student records. That link is often made through
    quasi-identifiers, not names, so it survives any amount of name removal.

    The test is a **linkage attack**: take a release with names and UNITIDs removed,
    join it back to the identified directory on its remaining columns, and count the
    records that match exactly one institution.
    """),
    code(r'''
    def linkage_attack(release, reference, keys):
        """Share of released rows whose quasi-identifiers match exactly one reference row."""
        candidates = reference.groupby(keys, dropna=False, observed=True).size().rename("n_matches")
        matched = release.join(candidates, on=keys)
        return float((matched["n_matches"] == 1).mean())


    naive_keys = ["STABBR", "SECTOR", "ENROLL_FALL"]
    naive = universe[naive_keys + ["RET_PCF"]].copy()
    print(f"naive release (state, sector, exact headcount): "
          f"{linkage_attack(naive, universe, naive_keys):.1%} re-identified")
    '''),
    md("""
    Exact headcount is effectively a fingerprint. Coarsening trades precision for
    anonymity: state becomes Census region (`OBEREG`), headcount becomes a size band, and
    the minimum equivalence-class size `k` becomes the measure of protection.
    """),
    code(r"""
    SIZE_BINS = [0, 500, 1_000, 2_500, 5_000, 10_000, 20_000, np.inf]
    SIZE_LABELS = ["<500", "500-999", "1k-2.5k", "2.5k-5k", "5k-10k", "10k-20k", "20k+"]

    coarse = universe.assign(SIZE_BAND=iu.coarsen(universe["ENROLL_FALL"], SIZE_BINS, SIZE_LABELS))
    coarse_keys = ["OBEREG", "SECTOR", "SIZE_BAND"]

    rows = []
    for label, frame, keys in [
        ("state + sector + exact headcount", universe, naive_keys),
        ("state + sector + size band", coarse, ["STABBR", "SECTOR", "SIZE_BAND"]),
        ("region + sector + size band", coarse, coarse_keys),
    ]:
        classes = iu.k_anonymity(frame, keys)
        rows.append({
            "quasi-identifiers": label,
            "min k": int(classes["class_size"].min()),
            "rows in classes of k<5": int(classes.loc[classes["class_size"] < 5, "class_size"].sum()),
            "re-identified": linkage_attack(frame[keys], frame, keys),
        })
    pd.DataFrame(rows).assign(**{"re-identified": lambda d: d["re-identified"].map("{:.1%}".format)})
    """),
    md("""
    Coarsening drives down re-identification but never to zero, because some
    institutions are unique on any reasonable description: the only large public
    university of its type in a region is unique however coarsely you describe it.
    Values released alongside the quasi-identifiers also leak. An exact retention rate
    joined to public IPEDS narrows the candidates again, so released outcome values
    are banded too.
    """),
    code(r"""
    released = coarse.assign(RET_BAND=iu.coarsen(coarse["RET_PCF"], list(range(0, 101, 10)) + [np.inf],
                                                 [f"{b}-{b + 9}" for b in range(0, 100, 10)] + ["100"]))
    for keys in (coarse_keys + ["RET_PCF"], coarse_keys + ["RET_BAND"]):
        print(f"{' + '.join(keys):45s} re-identified: {linkage_attack(released[keys], released, keys):.1%}")
    """),
    md("""
    ### Complementary suppression on a derived table

    Small cells in derived cross-tabulations are the realistic disclosure risk: a
    program-level count of women completers at a small institution can isolate one or
    two people. Colorado completions by CIP family and award level show the mechanism.
    Primary suppression alone leaks whenever a group's total is published and exactly
    one cell is blanked, because the blank can be recovered by subtraction.
    """),
    code(r'''
    comp, _ = iu.read_curated("c05_c", root="../data/curated")
    co_ids = universe.loc[universe["STABBR"] == "CO", "UNITID"]
    detail = comp[comp["UNITID"].isin(co_ids) & (comp["MAJORNUM"] == 1) & (comp["CIPCODE"] != "99")]
    table = (detail.assign(CIP_FAMILY=detail["CIPCODE"].str[:2])
                   .groupby(["UNITID", "AWLEVEL", "CIP_FAMILY"], as_index=False)["CTOTALW"].sum())

    primary, _ = iu.suppress(table, ["CTOTALW"], threshold=5, complementary=False)
    protected, audit = iu.suppress(table, ["CTOTALW"], threshold=5, complementary=True,
                                   group_cols=["UNITID", "AWLEVEL"])


    def recoverable(frame):
        """Multi-cell groups with exactly one blank: recoverable from the published group total."""
        keys = [frame["UNITID"], frame["AWLEVEL"]]
        blanks = frame["CTOTALW"].isna().groupby(keys).sum()
        cells = frame.groupby(keys).size()
        return int(((blanks == 1) & (cells > 1)).sum())


    print(f"{len(table):,} cells across {table.groupby(['UNITID', 'AWLEVEL']).ngroups:,} institution x level groups")
    print(f"primary only:        {int(primary['CTOTALW'].isna().sum()):>5,} cells blanked, "
          f"{recoverable(primary):,} multi-cell groups recoverable by subtraction")
    print(f"with complementary:  {int(protected['CTOTALW'].isna().sum()):>5,} cells blanked, "
          f"{recoverable(protected):,} multi-cell groups recoverable by subtraction")
    assert recoverable(protected) == 0
    audit
    '''),
    md("""
    The audit's last column counts the case suppression cannot fix. When an institution
    awards a level in only one CIP family, that single cell is the group total, so no
    complementary cell exists. Blanking it protects nothing while the level total is
    published elsewhere. `iu.suppress` counts these instead of passing them silently, and
    the release must suppress the matching totals as well.
    """),
    md("""
    Complementary suppression costs more blanked cells and leaves no multi-cell group
    recoverable by subtraction from its total. It does not defend against differencing across two
    releases with different groupings; for that, the governing policy has to fix the
    release schema.

    ### Pseudonymised public layer

    The public file replaces `UNITID` with a keyed-HMAC pseudonym. A bare hash would be
    worthless: with roughly six thousand institutions, anyone can hash every UNITID and
    invert the mapping in seconds. The key comes from the environment and is never
    written next to the data.
    """),
    code(r"""
    salt = os.environ.get("IPEDS_SALT")
    if not salt:
        import secrets
        salt = secrets.token_hex(32)
        print("IPEDS_SALT is not set: using a one-off key, so pseudonyms change on every run.\n"
              "Set IPEDS_SALT (see .env.example) for pseudonyms that stay joinable across releases.")

    public = released[["UNITID", "OBEREG", "SECTOR", "ICLEVEL", "SIZE_BAND", "RET_BAND"]].copy()
    public["INST_ID"], crosswalk = iu.synthetic_id(public["UNITID"], salt=salt, keep_map=True)
    public = public.drop(columns="UNITID")[["INST_ID", "OBEREG", "SECTOR", "ICLEVEL", "SIZE_BAND", "RET_BAND"]]
    public = public.astype({"OBEREG": "Int64", "SECTOR": "Int64", "ICLEVEL": "Int64"})

    Path("../data/public").mkdir(parents=True, exist_ok=True)
    public.to_parquet("../data/public/institutions_2023_public.parquet", index=False)
    print(f"public layer: {public.shape}; crosswalk of {len(crosswalk):,} ids kept in memory only")
    public.head()
    """),
    md("""
    ## Exercises

    1. Add `C21BASIC` to the coarsened quasi-identifiers. How far does the minimum `k`
       fall, and which Carnegie classes are responsible?
    2. Lower the suppression threshold to 3. How many fewer cells are blanked, and does
       any group become recoverable?
    3. The fall-headcount check flags one institution. Find it in both source files and
       decide which figure a panel should carry, and why.
    """),
]
