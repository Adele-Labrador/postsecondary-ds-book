from .common import LOAD_INST, SETUP, code, md

TITLE = "Distributions and Missingness"
FILE = "02_distributions_and_missingness.ipynb"

CELLS = [
    md("""
    # 02 — Distributions and Missingness

    **Chapter 4 companion.** Institutional data is dominated by scale. A few very large
    institutions set the mean, count outcomes are overdispersed, and a missing value
    usually means "not asked" rather than "not answered". Each section makes one of
    these properties measurable before any model sees the data.

    | | |
    |---|---|
    | Input | `data/analytic/institutions_2023.parquet` (from notebook 01), `data/curated/c05_c` |
    | Methods | Log-normal fit with QQ diagnostics, robust location and scale, Poisson vs negative-binomial GLMs, definitional ratios, structural vs non-response missingness |
    """),
    code(SETUP),
    code(LOAD_INST),
    md("""
    ## 1. Heavy tails: tuition revenue

    Revenue spans five orders of magnitude, so the mean describes almost no one. On a
    log scale the distribution is close to normal, which is what licenses modelling log
    revenue in notebook 07. The check below does not use a normality test, because with
    thousands of rows any test rejects a trivially small deviation. It compares tail
    mass instead: the share of log values beyond three standard deviations, against the
    0.27% a normal distribution predicts.
    """),
    code(r"""
    from scipy import stats

    rev = inst.loc[inst["TUITION_REVENUE"] > 0, "TUITION_REVENUE"]
    log_rev = np.log10(rev)
    print(f"{len(rev):,} institutions with positive tuition revenue "
          f"({(inst['TUITION_REVENUE'] <= 0).sum():,} zero or negative, {inst['TUITION_REVENUE'].isna().sum():,} not reported)")

    z = (log_rev - log_rev.mean()) / log_rev.std()
    pd.DataFrame({
        "dollars": [rev.mean(), rev.median(), stats.skew(rev), np.nan],
        "log10 dollars": [log_rev.mean(), log_rev.median(), stats.skew(log_rev), (z.abs() > 3).mean()],
    }, index=["mean", "median", "skewness", "share beyond 3 SD"])
    """),
    code(r"""
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    axes[0].hist(rev / 1e6, bins=80, color="#4C72B0")
    axes[0].set(xlabel="tuition revenue ($M)", ylabel="institutions", title="raw scale")
    axes[1].hist(log_rev, bins=50, density=True, color="#4C72B0", alpha=0.8)
    grid = np.linspace(log_rev.min(), log_rev.max(), 200)
    axes[1].plot(grid, stats.norm.pdf(grid, log_rev.mean(), log_rev.std()), color="k")
    axes[1].set(xlabel="log10 tuition revenue", title="log scale with normal fit")
    stats.probplot(log_rev, dist="norm", plot=axes[2])
    axes[2].set_title("QQ plot, log scale")
    save("02_tuition_lognormal")
    """),
    md("""
    The log scale removes almost all the skew, but the tails are asymmetric: the QQ
    plot bends at the lower end, where more institutions fall below -3 SD than above +3.
    The next cell lists them. They are very small less-than-two-year schools, plus
    institutions that are funded mainly through appropriations and charge little or no
    tuition. Public (GASB) tuition is also reported after deducting discounts and
    allowances, as the `F1B01` label says, so a public that covers most tuition through
    allowances reports almost none. For all of these institutions tuition revenue is a
    poor proxy for scale, so a model of log revenue (notebook 07) should be checked for
    residuals concentrated there.
    """),
    code(r"""
    tails = inst.loc[rev.index].assign(z=(log_rev - log_rev.mean()) / log_rev.std())
    print(f"below -3 SD: {(tails['z'] < -3).sum()}   above +3 SD: {(tails['z'] > 3).sum()}")
    (tails[tails["z"] < -3].sort_values("z")
         [["INSTNM", "SECTOR_LABEL", "TUITION_REVENUE", "TOTAL_REVENUES", "ENROLL_FALL"]].head(10))
    """),
    md("""
    ## 2. Robust location and scale: student-to-faculty ratio

    A handful of institutions report very high student-to-faculty ratios, mostly large
    online providers and small programs with few instructional staff. The comparison
    below removes the top 1% and asks which summaries move. The median and the scaled
    MAD (which estimates the SD under normality) barely change; the mean and SD do.
    """),
    code(r"""
    x = inst["STUFACR"].dropna()


    def summarize(s):
        return pd.Series({
            "n": len(s), "mean": s.mean(), "SD": s.std(), "median": s.median(),
            "MAD (normal-scaled)": stats.median_abs_deviation(s, scale="normal"),
            "IQR": s.quantile(0.75) - s.quantile(0.25),
        })


    trimmed = x[x <= x.quantile(0.99)]
    robust = pd.DataFrame({"all": summarize(x), "top 1% removed": summarize(trimmed)})
    robust["relative change"] = robust["top 1% removed"] / robust["all"] - 1
    robust
    """),
    code(r"""
    inst.nlargest(6, "STUFACR")[["INSTNM", "SECTOR_LABEL", "STUFACR", "ENROLL_FALL", "PCTE12DEEXC"]]
    """),
    md("""
    ## 3. Count outcomes are overdispersed

    Awards conferred are counts. The Poisson model assumes variance equal to the mean;
    institutional counts violate that badly, because institutions of the same size
    differ in program mix and completion. Before fitting, the count has to be built
    correctly. Completions files contain a CIP `99` row that is the grand total for each
    award level, plus detail rows for each program and a second-major block. Summing
    every row counts each award more than twice.
    """),
    code(r"""
    comp, _ = iu.read_curated("c05_c", root="../data/curated")
    first = comp["MAJORNUM"] == 1
    pd.Series({
        "every row": comp["CTOTALT"].sum(),
        "first-major detail rows (CIP != 99)": comp.loc[first & (comp["CIPCODE"] != "99"), "CTOTALT"].sum(),
        "first-major CIP 99 totals": comp.loc[first & (comp["CIPCODE"] == "99"), "CTOTALT"].sum(),
        "AWARDS_TOTAL in the analytic table": inst["AWARDS_TOTAL"].sum(),
    }).map("{:,.0f}".format).to_frame("awards")
    """),
    md("""
    The two first-major totals agree exactly, which is what the `rolls_up` rule in
    `c05_c` enforces. Summing every row roughly doubles the count.

    With the count settled, the models below regress awards on log fall enrollment. The
    Pearson dispersion statistic (chi-square / residual df) should be near 1 for a
    Poisson model that fits.
    """),
    code(r"""
    import statsmodels.api as sm

    counts = inst.dropna(subset=["AWARDS_TOTAL", "ENROLL_FALL"]).query("ENROLL_FALL > 0")
    y = counts["AWARDS_TOTAL"].to_numpy(dtype=float)
    X = sm.add_constant(np.log(counts["ENROLL_FALL"].to_numpy(dtype=float)))

    poisson = sm.GLM(y, X, family=sm.families.Poisson()).fit()
    negbin = sm.NegativeBinomial(y, X).fit(disp=False)

    pd.DataFrame({
        "Poisson": [poisson.aic, poisson.pearson_chi2 / poisson.df_resid, poisson.params[1], np.nan],
        "negative binomial (NB2)": [negbin.aic, np.nan, negbin.params[1], negbin.params[-1]],
    }, index=["AIC", "Pearson dispersion", "elasticity on log enrollment", "alpha (overdispersion)"])
    """),
    md("""
    A dispersion statistic far above 1 means Poisson standard errors are too small by
    roughly its square root, so every significance test built on them overstates
    certainty. The negative binomial absorbs the extra variance through `alpha`, and its
    far lower AIC confirms the better fit.

    The two models also disagree on the elasticity itself. Because Poisson assumes
    variance equals the mean, the largest institutions dominate its fit. The negative
    binomial down-weights them and finds a smaller elasticity, meaning awards grow less
    than proportionally with fall headcount. (Why that happens is a hypothesis for
    exercise 1, not a finding here.) A misspecified variance function changes the
    substantive answer, not just the standard errors.
    """),
    md("""
    ## 4. Enrollment is a definition, not a number

    Fall headcount and 12-month unduplicated headcount measure different populations.
    Their ratio is large where students enroll for short programs or start outside the
    fall term. The two windows also do not line up: `DRVEF122023` covers July 1, 2022 to
    June 30, 2023, while fall 2023 comes after that window closes. A ratio below 1
    therefore usually means growth between the two periods, not a data error.
    """),
    code(r"""
    ratio = inst.dropna(subset=["TWELVE_TO_FALL"])
    summary = (ratio.groupby("SECTOR_LABEL")["TWELVE_TO_FALL"]
                    .agg(institutions="size", median="median", share_below_1=lambda s: (s < 1).mean())
                    .sort_values("median", ascending=False))
    print(f"{(ratio['TWELVE_TO_FALL'] < 1).sum():,} institutions report more fall 2023 students than 2022-23 unduplicated students")
    summary
    """),
    code(r"""
    order = summary.index.tolist()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.boxplot([ratio.loc[ratio["SECTOR_LABEL"] == s, "TWELVE_TO_FALL"].clip(upper=6) for s in order],
               orientation="horizontal", showfliers=False)
    ax.set_yticks(range(1, len(order) + 1), order)
    ax.axvline(1, color="k", lw=0.8, ls="--")
    ax.set(xlabel="12-month unduplicated / fall headcount (clipped at 6)")
    save("02_twelve_to_fall")
    """),
    md("""
    ## 5. Missing by design versus missing by non-response

    Missingness in IPEDS is mostly structural: a survey item is not collected from an
    institution type, or an upstream screening question routes the institution past it.
    Treating structural gaps as random non-response, and imputing them, invents data for
    institutions that were never asked.
    """),
    code(r"""
    cols = ["RET_PCF", "BA_RATE_150", "L4_RATE_150", "ADMIT_RATE", "OM1TOTLAWDP8",
            "TUITION_SHARE", "TENURE_DENSITY", "LEXPTOTF"]
    missing = inst.groupby("SECTOR_LABEL")[cols].apply(lambda d: d.isna().mean())
    missing.map("{:.0%}".format)
    """),
    md("""
    The pattern is sectoral, and most of it is structural. Graduation-rate measures
    split cleanly by level: the bachelor's-cohort rate is 100% missing outside four-year
    institutions and the less-than-four-year rate is 100% missing inside them. Outcome
    Measures and tenure status are absent for every less-than-two-year institution.
    Admissions data covers only institutions without open admission, so its gaps mark a
    policy rather than a failure to report. The library block shows both kinds of
    missingness at once.
    """),
    code(r"""
    library = inst.assign(
        screening=inst["LEXP100K"].map({1: "1: expenditures >= $100K (detail collected)",
                                        2: "2: expenditures < $100K (detail skipped)"})
                                  .fillna(pd.Series(np.where(inst["LIB_FROM_PARENT"],
                                                             "no own report (parent value removed)",
                                                             "no Academic Libraries report"),
                                                    index=inst.index)),
    )
    pd.crosstab(library["screening"], library["LEXPTOTF"].isna().map({False: "present", True: "missing"}))
    """),
    md("""
    Every institution that answered `LEXP100K = 2` is missing the expenditure detail,
    and every institution that answered 1 has it. The gap is structural, so the correct
    treatment is a category ("small library") rather than an imputed dollar figure.
    Notebook 05 handles the library block this way.

    ## Exercises

    1. Fit the negative binomial with an additional `CONTROL` term. Does `alpha` fall,
       and what does that say about where the overdispersion comes from?
    2. For institutions with a 12-month/fall ratio below 0.8, compare fall 2022
       headcount (`EF2022A`) with fall 2023. Is growth the explanation?
    3. Plot `STUFACR` against `PCTE12DEEXC` (share exclusively online). How much of the
       upper tail does online delivery explain?
    """),
]
