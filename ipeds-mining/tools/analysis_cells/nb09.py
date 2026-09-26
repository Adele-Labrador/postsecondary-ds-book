from .common import LOAD_INST, SETUP, code, md

TITLE = "Longitudinal Trends in Retention"
FILE = "09_longitudinal_panel_models.ipynb"

CELLS = [
    md("""
    # 09 — Longitudinal Trends in Retention

    **Chapter 11 companion.** Did first-year retention fall for students who entered
    college during the pandemic, and did it recover? Answering that from IPEDS requires
    stacking six annual releases correctly, deciding which institutions to follow, and
    separating change within institutions from change in which institutions report.
    The notebook then works through a second, shorter series: published tuition and
    fees.

    | | |
    |---|---|
    | Input | `EF2018D` to `EF2023D` (six fall releases); `data/analytic/institutions_2023.parquet` for sector; `IC2023_AY` for tuition |
    | Outcome | `RET_PCF`: full-time retention rate, fall-to-fall |
    | Methods | Vintage stacking with reference-period checks, balanced vs unbalanced panels, two-way fixed effects with clustered standard errors, event-study coefficients by sector, compound annual growth |

    **Timing.** A retention rate in the fall `t` release describes students who entered
    in fall `t - 1` and returned in fall `t`. EF2021D is therefore the fall-2020
    entering cohort, the first to begin college during the pandemic. The notebook
    indexes everything by entering cohort to keep that straight.
    """),
    code(SETUP),
    code(LOAD_INST),
    md("""
    ## 1. Stack the vintages

    `iu.stack_vintages` fetches each release (revised versions where NCES published
    one), asserts that each dictionary's reference period reads "Fall {year}", and
    refuses duplicate institution-years. A mislabelled or shifted file fails here
    rather than appearing as a trend break.
    """),
    code(r"""
    panel, provenance = iu.stack_vintages("EF{year}D", range(2018, 2024), ["RET_PCF", "STUFACR", "RRFTCTA"],
                                          raw_dir="../data/raw")
    panel["COHORT"] = panel["YEAR"] - 1
    panel = panel.merge(inst[["UNITID", "SECTOR", "SECTOR_LABEL"]], on="UNITID", how="inner")
    print(pd.DataFrame(provenance)[["table", "period_check"]].to_string(index=False))
    panel.groupby("COHORT")["RET_PCF"].agg(["size", "count", "median"]).rename(
        columns={"size": "institution rows", "count": "with retention", "median": "median retention"})
    """),
    md("""
    Sector is taken from 2023 and assumed fixed. That is nearly always true, but an
    institution that converted from for-profit to nonprofit would be classified by its
    current status for every year. The merge also keeps only institutions still in the
    2023 universe. Closures appear as institutions that stop reporting, which the
    unbalanced panel reflects and the balanced panel removes.

    ## 2. Composition versus change: balanced and unbalanced panels

    An unbalanced sector mean can move because institutions improve, or because the
    set of reporting institutions changes. The balanced panel keeps only institutions
    with a retention rate for every cohort, so any movement in its mean is change
    within institutions.
    """),
    code(r"""
    sectors = {1: "Public 4-year", 2: "Private nonprofit 4-year", 3: "Private for-profit 4-year", 4: "Public 2-year"}
    panel = panel[panel["SECTOR"].isin(sectors)].assign(sector=lambda d: d["SECTOR"].map(sectors))
    bal = iu.balanced(panel, "RET_PCF")
    print(f"unbalanced: {panel['UNITID'].nunique():,} institutions; "
          f"balanced: {bal['UNITID'].nunique():,} observed in all {panel['COHORT'].nunique()} cohorts")

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    for ax, data, title in ((axes[0], panel, "unbalanced"), (axes[1], bal, "balanced")):
        for name, g in data.groupby("sector"):
            ax.plot(g.groupby("COHORT")["RET_PCF"].mean(), "o-", label=name)
        ax.axvspan(2019.5, 2020.5, color="#DDDDDD", zorder=0)
        ax.set(title=title, xlabel="entering cohort (fall)")
    axes[0].set_ylabel("mean full-time retention (%)")
    axes[1].legend(fontsize=8)
    save("09_balanced_vs_unbalanced")
    """),
    code(r"""
    trend = pd.concat({
        "unbalanced": panel.groupby(["sector", "COHORT"])["RET_PCF"].mean().unstack(),
        "balanced": bal.groupby(["sector", "COHORT"])["RET_PCF"].mean().unstack(),
    })
    trend.round(1)
    """),
    md("""
    Both panels show the same shape, but not the same levels. The balanced means sit
    0.1 to 1.1 points higher for four-year publics and nonprofits, because institutions
    that report every year are more established. In public two-year colleges the two panels
    are nearly identical, since almost all of them report every year. Before reading a
    trend, check that it survives balancing. The for-profit series moves most between
    the two, because its membership turns over most.

    ## 3. Two-way fixed effects and an event study

    Institution fixed effects remove every stable institutional difference. Cohort
    dummies then trace the average within-institution change relative to a reference
    cohort. The reference is the fall-2018 cohort, the last to complete its first year
    before the pandemic. The fall-2019 cohort's return in fall 2020 was already
    disrupted.

    The model is estimated on the within-transformed balanced panel. Standard errors are
    clustered by institution, since the same institution's years are correlated.
    Estimating each sector separately gives the sector interactions directly.
    """),
    code(r"""
    import statsmodels.api as sm

    REF = 2018


    def event_study(data):
        d = data.dropna(subset=["RET_PCF"]).copy()
        dummies = pd.get_dummies(d["COHORT"], prefix="c", dtype=float).drop(columns=f"c_{REF}")
        d = pd.concat([d, dummies], axis=1)
        cols = ["RET_PCF", *dummies.columns]
        w = iu.within_transform(d, "UNITID", cols)
        fit = sm.OLS(w["RET_PCF"], w[dummies.columns]).fit(cov_type="cluster", cov_kwds={"groups": w["UNITID"]})
        ci = fit.conf_int()
        out = pd.DataFrame({"estimate": fit.params, "lo": ci[0], "hi": ci[1]})
        out.index = [int(c.split("_")[1]) for c in out.index]
        out.loc[REF] = 0.0
        return out.sort_index()


    effects = {name: event_study(g) for name, g in bal.groupby("sector")}
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, (name, e) in enumerate(effects.items()):
        x = e.index + (i - 1.5) * 0.08
        ax.errorbar(x, e["estimate"], yerr=[e["estimate"] - e["lo"], e["hi"] - e["estimate"]],
                    fmt="o-", capsize=2, label=name)
    ax.axhline(0, color="k", lw=0.8)
    ax.axvline(REF, color="#999999", ls=":")
    ax.set(xlabel="entering cohort (fall)", ylabel=f"change vs {REF} cohort (points)")
    ax.legend(fontsize=8)
    save("09_event_study")
    pd.concat({k: v.apply(lambda r: f"{r['estimate']:+.2f} [{r['lo']:+.2f}, {r['hi']:+.2f}]", axis=1)
               for k, v in effects.items()}, axis=1)
    """),
    md("""
    The timing of the dip differs by sector, and the cohort indexing makes that visible:

    - **Public two-year colleges** dip first. The fall-2019 cohort, whose return in fall
      2020 fell in the first pandemic autumn, is 1.4 points below the reference, and
      the fall-2020 cohort about 1 point below. By the fall-2022 cohort retention is
      2.1 points above the pre-pandemic level.
    - **Public four-year institutions** peak with the fall-2019 cohort (+1.2) and dip
      with the fall-2020 cohort (-2.0). They are back to the reference by the fall-2022
      cohort, with the interval spanning zero.
    - **Private nonprofits** sit a steady 0.6 to 0.8 points below the reference in
      every cohort after it, including 2017. That is a flat series with a high
      reference year, not a pandemic effect.
    - **For-profit four-year institutions** show the largest estimated declines
      (-4.6 and -5.4 points), with no recovery by the fall-2022 cohort. The intervals
      are several points wide, since the balanced group is small and heterogeneous.

    These are within-institution changes among survivors. They describe what happened
    at institutions that kept reporting, not the sector as it existed in 2018.

    ## 4. Tuition trajectories: a short wide series

    `IC2023_AY` carries four years of published in-state tuition and fees in one file:
    `CHG2AY0` (2020-21) to `CHG2AY3` (2023-24). Wide-to-long reshaping turns it into a
    panel. Compound annual growth summarises each institution's trajectory, and growth
    is nominal. Deflating needs an external price index, which is exercise 2.
    """),
    code(r"""
    record = iu.fetch("IC2023_AY", raw_dir="../data/raw")
    ay = iu.read_csv(record["data_path"], usecols=["UNITID", "CHG2AY0", "CHG2AY1", "CHG2AY2", "CHG2AY3"])
    long = ay.melt(id_vars="UNITID", var_name="item", value_name="price")
    long["YEAR"] = long["item"].str[-1].astype(int).map({0: 2020, 1: 2021, 2: 2022, 3: 2023})
    complete = long.dropna(subset=["price"]).query("price > 0").groupby("UNITID").filter(lambda g: len(g) == 4)

    wide = complete.pivot(index="UNITID", columns="YEAR", values="price")
    wide["CAGR"] = (wide[2023] / wide[2020]) ** (1 / 3) - 1
    wide = wide.join(inst.set_index("UNITID")[["CONTROL_LABEL", "ICLEVEL"]], how="inner")
    wide["level"] = wide["ICLEVEL"].map({1: "4-year", 2: "2-year", 3: "less than 2-year"})
    print(f"{len(wide):,} institutions with four positive published prices")
    wide.groupby(["CONTROL_LABEL", "level"])["CAGR"].describe()[["count", "25%", "50%", "75%"]].mul(
        [1, 100, 100, 100]).round(2).rename(columns=lambda c: c if c == "count" else f"{c} (% per year)")
    """),
    code(r"""
    frozen = (wide[2023] == wide[2020]).groupby(wide["CONTROL_LABEL"]).mean()
    frozen.rename("share with identical 2020-21 and 2023-24 prices").to_frame().round(3)
    """),
    md("""
    Median nominal growth from 2020-21 to 2023-24 was about 3% a year at four-year
    nonprofits, 1.8% at four-year publics, and 1.2% at public two-year colleges. The
    lower quartile is exactly zero for public two-year and all for-profit groups: about
    15% of public and 14% of for-profit institutions charged the same price in 2023-24
    as in 2020-21. Tuition freezes show up as zero growth, and they are common enough
    to shape the lower quartile. A median growth rate therefore mixes two groups, frozen and
    rising prices. Reporting the share frozen alongside the median separates them.

    **Series availability.** Several derived tables used elsewhere in the book, such as
    `DRVGR` and `DRVEF12`, are published under these names only for recent years;
    earlier years return a 404. Before building a longer panel, list which vintages exist
    rather than assuming a continuous series.

    ## Exercises

    1. Weight the event study by cohort size (`RRFTCTA`). Do large institutions show a
       smaller pandemic dip than the average institution?
    2. Deflate the tuition series with the CPI-U and recompute CAGR in real terms. Which
       sector's real price fell?
    3. Compare `CHG2AY3` with `TUITION2 + FEE2` from the same file. When do they differ,
       and which should a trend analysis use?
    """),
]
