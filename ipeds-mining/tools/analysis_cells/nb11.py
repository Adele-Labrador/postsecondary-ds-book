from .common import SETUP, code, md

TITLE = "Colorado Performance Funding (HB 20-1366)"
FILE = "11_colorado_performance_funding.ipynb"

CELLS = [
    md("""
    # 11 — Colorado Performance Funding (HB 20-1366)

    **Chapter 13 capstone.** Since FY 2021-22, Colorado has allocated most state
    operating funding for its ten public governing boards through Step 2 of the
    HB 20-1366 model. The model scores eight metrics, three of them outcome rates from
    IPEDS. This notebook rebuilds the formula from public data, tests the rebuild
    against what the legislature actually appropriated, and then asks what the formula
    rewards.

    | | |
    |---|---|
    | Inputs | `EF{y}D`, `EF{y}A`, `GR{y}` (2017-2023), `SFA` (2016-17 to 2022-23), `C{y}_A` (2018-2024); board funding and resident FTE from `dashboard/data/colorado.json` in the parent repository |
    | Unit | Governing board (the formula's unit); institutions are aggregated to boards |
    | Methods | Formula reconstruction, out-of-sample validation against appropriations, sensitivity analysis, counterfactual allocation, disaggregated completion gaps |
    | Outputs | `reports/funding/fy2025_26_reconstruction.csv`, `reports/figures/11_*.png` |

    **Policy boundary.** HB 20-1366 governs FY 2021-22 to FY 2026-27. HB 26-1345
    ([bill page](https://leg.colorado.gov/bills/hb26-1345)) replaces it from FY 2027-28
    with "results-informed funding", which redefines the metrics and drops the
    sequential Step 1-2-3 calculation. Nothing here describes the new model.

    **Scope.** This is an institution- and board-level analysis. It does not score
    students, and demographic fields are used only to describe group patterns.
    """),
    code(SETUP),
    md("""
    ## 1. Board funding and resident FTE

    The parent repository's Colorado panel (`src/ingest/colorado.py`) already parses
    each board's formula funding from Joint Budget Committee documents, with a page
    citation per value, plus CDHE's resident FTE series. The notebook reads that file
    rather than parsing the PDFs again. Outside the repository, it downloads the
    same file from GitHub.
    """),
    code(r"""
    import json
    import urllib.request

    F = iu.funding
    RAW = Path("../data/raw")
    REPORTS = Path("../reports/funding")
    REPORTS.mkdir(parents=True, exist_ok=True)

    local = Path("../../dashboard/data/colorado.json")
    remote = ("https://raw.githubusercontent.com/Adele-Labrador/postsecondary-ds-book/"
              "main/dashboard/data/colorado.json")
    if local.exists():
        colorado = json.loads(local.read_text())
        print(f"read {local}")
    else:
        cache = RAW / "colorado.json"
        if not cache.exists():
            RAW.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(urllib.request.urlopen(remote, timeout=60).read())
        colorado = json.loads(cache.read_text())
        print(f"read {remote}")

    state_boards = [b for b in colorado["boards"] if b["state"]]
    fund = pd.DataFrame({b["id"]: b["funding"] for b in state_boards},
                        index=colorado["meta"]["fundingYears"]).T
    fte = pd.DataFrame({b["id"]: b["fte"]["resident"] for b in state_boards},
                       index=colorado["meta"]["fteYears"]).T
    names = {b["id"]: b["name"] for b in state_boards}
    roster = pd.DataFrame([{k: i[k] for k in ("name", "board", "unitid")}
                           for i in colorado["institutions"]])
    roster = roster[roster["board"].isin(fund.index)]
    board_of = roster.groupby("unitid")["board"].first()
    print(f"{len(fund)} governing boards, {board_of.size} IPEDS UNITIDs, "
          f"funding {fund.columns[0]} to {fund.columns[-1]}")
    (fund[["FY 2023-24", "FY 2024-25", "FY 2025-26"]] / 1e6).round(1).assign(
        **{"FY 2025-26 change %": (fund["FY 2025-26"] / fund["FY 2024-25"] - 1) * 100})
    """),
    md("""
    The FY 2025-26 Long Bill provided a 2.5% increase, all of it through Step 2. Had
    every board received exactly 2.5%, performance would have moved nothing. Instead,
    increases range from 2.0% (Adams State) to 3.4% (MSU Denver). That spread is the
    formula's output, and the target the reconstruction has to hit.

    Several boards govern more than one campus. CU has four rows in CDHE's FTE reports and three
    IPEDS UNITIDs, because Denver and Anschutz report to IPEDS together. Board-level
    funding hides how each board divides money among its campuses.

    ## 2. The mechanics

    For each metric and board, CDHE computes `D`, the four-year average divided by the
    average of its three oldest years. It multiplies `D` by the board's share of
    prior-year funding and renormalises. The weighted sum across metrics is the board's
    Step 2 share. The first check reproduces the worked example in CDHE's
    [data definitions](https://cdhe.colorado.gov/sites/highered/files/Colorado_Performance_Funding_Overview_and_Data_Definitions_2025_26_1.pdf).
    """),
    code(r"""
    prior = pd.Series([0.10, 0.20, 0.70], index=["Board X", "Board Y", "Board Z"])
    d = pd.Series([105 / 100, 550 / 500, 910 / 900], index=prior.index)
    example = pd.DataFrame({"A prior share": prior, "D": d, "F allocation": F.metric_allocation(prior, d)})
    assert (example["F allocation"] * 100).round(1).tolist() == [10.2, 21.3, 68.5]
    (example * 100).round(1)
    """),
    md("""
    The example matches the published table to one decimal. Two properties of the
    arithmetic matter for everything that follows.

    First, `D = 0.75 + 0.25 × x₄ / mean(x₁, x₂, x₃)`. Only the newest year moves `D`,
    and by a quarter of its change relative to the prior mean. Second, the reward for a
    lasting improvement is front-loaded and then stops. A board that raises a metric 1%
    and holds it there gains on that metric for three windows. After that, the higher
    level is the baseline and `D` returns to 1. The cell below traces that path. The
    gain does not disappear, though: it becomes part of the prior-year share that every
    later allocation starts from.
    """),
    code(r"""
    def reward_path(step=0.01, windows=6):
        level = np.r_[np.ones(3), np.full(windows + 3, 1 + step)]
        return pd.Series([F.d_ratio(level[i:i + 4]) - 1 for i in range(windows)],
                         index=pd.RangeIndex(1, windows + 1, name="window after the step"))

    path = (reward_path() * 100).rename("D - 1 (%) after a lasting 1% improvement")
    print(path.round(3).to_string())
    print(f"cumulative D - 1 over all windows: {path.sum():.3f}%")
    """),
    md("""
    A lasting 1% improvement raises `D` by 0.25%, then 0.17%, then 0.08%, then
    nothing: half of the improvement, spread over three years. Because each board's
    allocation is renormalised against all the others, what counts is improving faster
    than the other boards, not improving at all.

    ## 3. What IPEDS can and cannot rebuild

    Only half of the Step 2 weight can be measured from data the formula actually uses.
    Retention and the two graduation rates come from IPEDS for every board except eight
    CCCS colleges. Resident FTE comes from the same CDHE series the formula uses. The
    other four metrics come from SURDS, the state's student-unit records, which are not
    public. IPEDS proxies stand in for three of them. First-generation status has no
    IPEDS equivalent, so that metric is held neutral, which leaves every board's
    allocation on it equal to its prior share.
    """),
    code(r"""
    fidelity = pd.DataFrame(F.METRICS).T.assign(weight=pd.Series(F.WEIGHTS))
    fidelity[["label", "weight", "fidelity", "proxy"]].sort_values("weight", ascending=False)
    """),
    md("""
    ## 4. Build the metric panel from IPEDS

    Every file is checked against its own dictionary before use. The fall surveys must
    read "Fall {y}". The GR files must name their 4-year cohort year, because GR mixes
    two cohorts in one file (four-year institutions six years back, two-year
    institutions three years back). The SFA aid year and the Completions award year are
    checked the same way. The panel is long: one row per institution, metric, and year,
    with a numerator, a denominator, and the cohort definition used (`src`).
    """),
    code(r"""
    U = board_of.index


    def load(table, expect, cols=None):
        record = iu.fetch(table, raw_dir=RAW)
        iu.assert_reference_period(record["dict_path"], expect=expect, table=table)
        frame = iu.read_csv(record["data_path"], usecols=cols)
        return frame[frame["UNITID"].isin(U)]


    rows = []
    for y in range(2017, 2024):
        ef = load(f"EF{y}D", f"Fall {y}", ["UNITID", "RRFTCTA", "RET_NMF"])
        rows += [dict(UNITID=r.UNITID, metric="retention", year=y, num=r.RET_NMF, den=r.RRFTCTA)
                 for r in ef.itertuples()]

        gr = load(f"GR{y}", rf"cohort year {y - 6} \(4-year\)", ["UNITID", "GRTYPE", "GRTOTLT"])
        gr = gr.pivot_table(index="UNITID", columns="GRTYPE", values="GRTOTLT", aggfunc="sum")
        for unitid, g in gr.iterrows():
            if pd.notna(g.get(8)):       # bachelor's subcohort at a four-year institution
                spec = ("BA subcohort", g[8], g.get(13), g.get(12))
            elif pd.notna(g.get(29)):    # degree/certificate cohort at a two-year institution
                spec = ("2-yr cohort", g[29], g.get(35), g.get(30))
            elif pd.notna(g.get(2)):     # four-year institution with no bachelor's subcohort
                spec = ("4-yr total cohort", g[2], np.nan, g.get(3))
            else:
                continue
            src, cohort, on_time, within_150 = spec
            rows.append(dict(UNITID=unitid, metric="grad100", year=y, num=on_time, den=cohort, src=src))
            rows.append(dict(UNITID=unitid, metric="grad150", year=y, num=within_150, den=cohort, src=src))

        ea = load(f"EF{y}A", f"Fall {y}")
        ea = ea[ea["EFALEVEL"] == 1]
        rows += [dict(UNITID=r.UNITID, metric="urm_share", year=y,
                      num=r.EFBKAAT + r.EFHISPT + r.EFAIANT, den=r.EFTOTLT - r.EFNRALT)
                 for r in ea.itertuples()]

    for y in range(2016, 2024):  # SFA aid year y-(y+1) stands for fall y
        table = f"SFA{y % 100:02d}{(y + 1) % 100:02d}"
        try:
            sfa = load(table, f"{y}-{(y + 1) % 100:02d}", ["UNITID", "UPGRNTN", "SCUGRAD"])
        except iu.FetchError:
            print(f"{table} not published yet: fall {y} Pell share unavailable")
            continue
        rows += [dict(UNITID=r.UNITID, metric="pell_share", year=y, num=r.UPGRNTN, den=r.SCUGRAD)
                 for r in sfa.itertuples()]

    for y in range(2018, 2025):
        c = load(f"C{y}_A", f"July 1, {y - 1} and June 30, {y}",
                 ["UNITID", "CIPCODE", "MAJORNUM", "CTOTALT"])
        c = c[(c["CIPCODE"] == "99") & (c["MAJORNUM"] == 1)]
        rows += [dict(UNITID=u, metric="credentials", year=y, num=v, den=np.nan)
                 for u, v in c.groupby("UNITID")["CTOTALT"].sum().items()]

    panel = pd.DataFrame(rows)
    panel["board"] = panel["UNITID"].map(board_of)
    panel["src"] = panel["src"].fillna("")
    panel.groupby(["metric", "year"])["UNITID"].nunique().unstack("metric")
    """),
    md("""
    ## 5. The reclassification trap

    Eight CCCS colleges began awarding bachelor's degrees, and IPEDS reclassified them
    as four-year institutions. At a four-year institution, IPEDS counts only
    bachelor's seekers in the retention cohort and reports no 100%-time rate for
    associate seekers. The cohort an IPEDS-based formula would read collapses.
    """),
    code(r"""
    names_hd = iu.read_csv(iu.fetch("HD2023", raw_dir=RAW)["data_path"], usecols=["UNITID", "INSTNM"])
    instnm = names_hd.set_index("UNITID")["INSTNM"]
    cccs = panel[(panel["board"] == "CCCS") & (panel["metric"] == "retention")]
    trap = cccs.pivot_table(index="UNITID", columns="year", values="den").rename(index=instnm)
    trap.astype("Int64").sort_values(2017, ascending=False)
    """),
    code(r"""
    totals = trap.sum()
    print(f"CCCS full-time retention cohort in IPEDS: {totals[2017]:,.0f} students (fall 2016 entrants) "
          f"-> {totals[2023]:,.0f} (fall 2022 entrants)")
    """),
    md("""
    Front Range's retention cohort falls from about 1,100 students to zero, and Pikes
    Peak's from about 1,050. Across CCCS, the IPEDS cohort shrinks by about three
    quarters (5,384 to 1,207 students), almost all of it because of how these colleges are classified, not because
    fewer students enrolled. CDHE computes these colleges' rates from SURDS, following
    IPEDS methodology, which is why the
    [FY 2026-27 JBC briefing](https://content.leg.colorado.gov/sites/default/files/fy2026-27_hedbrf.pdf)
    recommends SURDS for all institutions.

    The reconstruction keeps an institution in a metric only if it reports under one
    definition, with a positive cohort, in every year of the window
    (`iu.funding.consistent_reporters`). For CCCS this means the rates rest on the
    colleges that never changed classification. The rate's level is then
    unrepresentative, but its change over the window is still measured within the same
    colleges.

    ## 6. Reconstruct FY 2025-26

    CDHE documents the FY 2024-25 windows (fall 2019 to fall 2022, GR cohorts ending in
    the GR2022 release, credentials through 2022-23) and states that the FY 2025-26
    graduation rates start from the fall 2017 cohort. FY 2025-26 is therefore fall 2020
    to fall 2023, which `F.formula_window` encodes. The prior share is each board's
    share of FY 2024-25 funding. SFA 2023-24 is not yet published, so the Pell proxy
    uses fall 2019 to fall 2022, one year behind the formula; the cell output flags this.
    """),
    code(r"""
    def board_d(fy_start, *, how="pooled", shift=0, drop=()):
        d = pd.DataFrame(index=fund.index)
        notes = {}
        for metric in ["retention", "grad100", "grad150", "urm_share", "pell_share", "credentials"]:
            if metric in drop:
                continue
            years = [y + shift for y in F.formula_window(fy_start, metric)]
            sub = panel[panel["metric"] == metric]
            if years[-1] > sub["year"].max():           # newest year not yet published
                years = [y - 1 for y in years]
                notes[metric] = f"window shifted back to {years[0]}-{years[-1]}"
            series = F.board_series(sub, years, how=how)
            d[metric] = series.apply(F.d_ratio, axis=1)
            notes.setdefault(metric, f"{years[0]}-{years[-1]}, {F.consistent_reporters(sub, years).size} institutions")
        if "resident_fte" not in drop:
            fy = [F.fiscal_year_label(y + shift) for y in F.formula_window(fy_start, "resident_fte")]
            d["resident_fte"] = fte[fy].apply(F.d_ratio, axis=1)
            notes["resident_fte"] = f"{fy[0]} to {fy[-1]} (CDHE)"
        return d, notes


    def predict(fy_start, **kw):
        base = fund[F.fiscal_year_label(fy_start - 1)]
        new = fund[F.fiscal_year_label(fy_start)]
        d, notes = board_d(fy_start, **kw)
        shares = F.step2_shares(base, d)
        return (shares * new.sum() / base - 1) * 100, d, notes


    T = 2025
    actual = (fund[F.fiscal_year_label(T)] / fund[F.fiscal_year_label(T - 1)] - 1) * 100
    pred, D, notes = predict(T)
    print(pd.Series(notes).to_string())
    D.round(4)
    """),
    code(r"""
    result = pd.DataFrame({"actual %": actual, "reconstructed %": pred})
    result["error (pts)"] = result["reconstructed %"] - result["actual %"]
    r = np.corrcoef(result["actual %"], result["reconstructed %"])[0, 1]
    rmse = np.sqrt((result["error (pts)"] ** 2).mean())
    print(f"correlation {r:.2f}; RMSE {rmse:.2f} percentage points; "
          f"spread of actual increases {actual.min():.2f}% to {actual.max():.2f}%")
    result.assign(board=pd.Series(names)).to_csv(REPORTS / "fy2025_26_reconstruction.csv")

    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    ax.scatter(result["actual %"], result["reconstructed %"], color="#20808D")
    offsets = {"CCCS": (2, 7), "CU": (7, -6), "UNC": (-30, 2), "CMU": (6, -10)}
    for b, row in result.iterrows():
        ax.annotate(b, (row["actual %"], row["reconstructed %"]), xytext=offsets.get(b, (4, 2)),
                    textcoords="offset points", fontsize=8)
    lim = [0.5, 4.3]
    ax.plot(lim, lim, color="k", lw=0.8, ls="--")
    ax.axhline(2.5, color="#A84B2F", lw=0.8, ls=":")
    ax.set(xlim=lim, ylim=lim, xlabel="actual FY 2025-26 increase (%)",
           ylabel="reconstructed from IPEDS + CDHE FTE (%)")
    save("11_reconstruction_fy2025_26")
    result.round(2)
    """),
    md("""
    The reconstruction tracks the pattern of actual increases (correlation 0.83, RMSE
    0.50 points) using only public data, with half the weight measured by proxies. It
    places MSU Denver first and Adams State last, as the Long Bill did. The two largest
    errors point the same way: MSU's gain is overstated by about 0.6 points, and Adams
    State's is understated by more than a point. Adams State's IPEDS graduation rates
    fall sharply in the window (`D` about 0.96 for both), and its prior share includes
    the FY 2024-25 Step 1 money. Either the SURDS metrics moved in its favour, or an
    adjustment outside Step 2 is involved. The public data cannot say which.

    ### Is the fit an accident?

    A reconstruction with this many choices can fit by luck. The next cell varies one
    choice at a time: shifting every window back a year, averaging institution rates
    instead of pooling counts, and dropping the proxy metrics.
    """),
    code(r"""
    variants = {
        "documented windows (baseline)": {},
        "every window one year earlier": {"shift": -1},
        "mean of institution rates": {"how": "mean"},
        "Pell proxy held neutral": {"drop": ("pell_share",)},
        "Pell and URM proxies neutral": {"drop": ("pell_share", "urm_share")},
        "IPEDS rates only (+FTE neutral)": {"drop": ("pell_share", "urm_share", "credentials", "resident_fte")},
        "resident FTE only": {"drop": ("pell_share", "urm_share", "credentials", "retention", "grad100", "grad150")},
    }
    rows = []
    for label, kw in variants.items():
        p, _, _ = predict(T, **kw)
        rows.append({"variant": label, "correlation": np.corrcoef(actual, p)[0, 1],
                     "RMSE (pts)": np.sqrt(((p - actual) ** 2).mean()),
                     "ASU": p["ASU"], "MSU": p["MSU"]})
    pd.DataFrame(rows).set_index("variant").round(2)
    """),
    md("""
    Shifting the windows by one year drops the correlation from 0.83 to zero, so the
    documented windows carry real information and the fit is not generic. Pooling
    counts and averaging rates give almost the same answer. Each proxy that is
    neutralised lowers the correlation, which suggests the proxies carry some of the
    signal SURDS provides, imperfectly. FTE alone is slightly negatively related to the actual pattern.
    Under this model, enrollment change was not what drove FY 2025-26.

    **FY 2024-25 is not a clean second test.** The FY 2023-24 and FY 2024-25 amounts
    come from different JBC documents, and CU's increase (13.1%, against a 10.3% pool)
    is larger than any Step 2 reallocation could produce. Both points suggest a
    non-formula adjustment, so that year is not used for validation.

    ## 7. How much money does performance move?

    The formula re-divides the whole base every year, which sounds like a lot of
    money at stake. The counterfactual is a uniform 2.5% increase.
    """),
    code(r"""
    moved = F.redistribution(fund["FY 2024-25"], fund["FY 2025-26"])
    total = moved["moved"].clip(lower=0).sum()
    print(f"FY 2025-26 Step 2 total ${moved['actual'].sum() / 1e6:,.1f}M; moved relative to a "
          f"uniform increase ${total / 1e6:.2f}M ({total / moved['actual'].sum():.3%} of the total)")

    # FY 2026-27 request, 'FY 2026-27 Step 2 Formula Adjust' column (JBC briefing, HED-brf 35)
    request = pd.Series({"ASU": -534_929, "CMU": 421_481, "MSU": -248_931, "WCU": -291_005,
                         "CSU": 88_169, "FLC": -410_724, "CU": 385_481, "CSM": 336_094,
                         "UNC": 31_334, "CCCS": 223_031})
    print(f"FY 2026-27 request: Step 2 formula adjustments net to ${request.sum():,}; "
          f"${request.clip(lower=0).sum() / 1e6:.2f}M moves between boards")
    (moved.assign(**{"FY 2026-27 request adj.": request})[["actual_pct", "moved", "FY 2026-27 request adj."]]
     .rename(columns={"actual_pct": "FY 2025-26 %", "moved": "FY 2025-26 moved ($)"})
     .round(2))
    """),
    md("""
    About $1.1 million moved between boards in FY 2025-26, under 0.1% of a $1.25 billion
    allocation. The FY 2026-27 request moves about $1.5 million. The formula re-divides
    the whole base each year, but the prior-year share anchors almost all of it, and
    `D` ratios close to one move little. The result is stability, and a small
    incentive at the margin.

    ## 8. What is a retention point worth?

    The cell below raises one board's retention rate by one percentage point in the
    newest window year, leaves every other metric and board unchanged, and recomputes
    the FY 2025-26 allocation. Dividing by the extra students retained (1% of the board's
    measured cohort) puts the incentive in per-student terms.
    """),
    code(r"""
    years = F.formula_window(T, "retention")
    ret = panel[panel["metric"] == "retention"]
    rates = F.board_series(ret, years)
    keep = F.consistent_reporters(ret, years)
    cohort = ret[ret["UNITID"].isin(keep) & (ret["year"] == years[-1])].groupby("board")["den"].sum()

    base = fund["FY 2024-25"]
    pot = fund["FY 2025-26"].sum()
    s0 = F.step2_shares(base, D)
    value = {}
    for b in fund.index:
        bumped = rates.copy()
        bumped.loc[b, years[-1]] += 0.01
        d1 = D.assign(retention=bumped.apply(F.d_ratio, axis=1))
        dollars = (F.step2_shares(base, d1)[b] - s0[b]) * pot
        value[b] = {"retention %": rates.loc[b, years[-1]] * 100, "measured cohort": cohort[b],
                    "$ per point": dollars, "$ per extra retained student": dollars / (0.01 * cohort[b]),
                    "state $ per resident FTE": fund.loc[b, "FY 2025-26"] / fte.loc[b, "FY 2023-24"]}
    value = pd.DataFrame(value).T
    value.loc["CCCS", "$ per extra retained student"] = np.nan  # cohort is the consistent-reporter subset
    value.round(0)
    """),
    md("""
    A one-point retention gain is worth about $190,000 a year to CCCS, $150,000 to CU,
    and $120,000 to the CSU System, and under $50,000 to every board except MSU Denver. Per additional retained
    student, that is roughly $1,300 to $8,400 in a single year, depending on the board:
    well below the state's funding per resident FTE, which runs from about $6,400 to
    $17,700. The CCCS per-student figure is blanked because its IPEDS cohort is the
    consistent-reporter subset from section 5, not the colleges' real cohort.

    Two caveats keep this from being a cost-benefit calculation. A retained student
    also adds FTE (10% weight) and, eventually, a credential and a graduation-rate
    count. And tuition revenue is likely a larger incentive than the state's Step 2
    increment. Still, the formula's direct reward for retention is small relative to
    the cost of the student support it is meant to encourage.

    ## 9. Equity lens: access is rewarded, gaps are not

    Forty percent of Step 2 rewards growth in the resident Pell and URM enrollment
    shares. No metric rewards closing completion gaps: retention and graduation enter
    as overall rates. The GR files report completers by race and ethnicity, so the gap
    between underrepresented-minority students (Black, Hispanic, American Indian or
    Alaska Native) and other U.S. students with known race can be tracked for the
    four-year boards, whose bachelor's subcohort is defined consistently.
    """),
    code(r"""
    cols = ["UNITID", "GRTYPE", "GRTOTLT", "GRBKAAT", "GRHISPT", "GRAIANT", "GRNRALT", "GRUNKNT"]
    gap_rows = []
    for y in range(2017, 2024):
        g = load(f"GR{y}", rf"cohort year {y - 6} \(4-year\)", cols)
        g = g[g["GRTYPE"].isin([8, 12])].assign(board=lambda x: x["UNITID"].map(board_of))
        g = g[g["board"] != "CCCS"]
        g["URM"] = g["GRBKAAT"] + g["GRHISPT"] + g["GRAIANT"]
        g["other"] = g["GRTOTLT"] - g["URM"] - g["GRNRALT"] - g["GRUNKNT"]
        s = g.groupby(["board", "GRTYPE"])[["URM", "other"]].sum().unstack("GRTYPE")
        for b, r in s.iterrows():
            gap_rows.append({"board": b, "cohort": y - 6, "urm_n": r[("URM", 8)], "urm_k": r[("URM", 12)],
                             "oth_n": r[("other", 8)], "oth_k": r[("other", 12)]})
    gaps = pd.DataFrame(gap_rows)


    def period_gap(frame):
        pu, po = frame["urm_k"].sum() / frame["urm_n"].sum(), frame["oth_k"].sum() / frame["oth_n"].sum()
        se = np.sqrt(pu * (1 - pu) / frame["urm_n"].sum() + po * (1 - po) / frame["oth_n"].sum())
        return pd.Series({"URM %": pu * 100, "other %": po * 100, "gap (pts)": (po - pu) * 100,
                          "±95% (pts)": 1.96 * se * 100, "URM cohort": frame["urm_n"].sum()})


    early = gaps[gaps["cohort"].between(2011, 2013)].groupby("board").apply(period_gap)
    late = gaps[gaps["cohort"].between(2015, 2017)].groupby("board").apply(period_gap)
    equity = pd.concat({"cohorts 2011-13": early, "cohorts 2015-17": late}, axis=1)
    equity[("change", "gap (pts)")] = late["gap (pts)"] - early["gap (pts)"]
    equity.round(1)
    """),
    code(r"""
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    order = late["gap (pts)"].sort_values().index
    yy = np.arange(len(order))
    ax.errorbar(early.loc[order, "gap (pts)"], yy - 0.15, xerr=early.loc[order, "±95% (pts)"],
                fmt="o", color="#BBBBBB", label="cohorts 2011-13")
    ax.errorbar(late.loc[order, "gap (pts)"], yy + 0.15, xerr=late.loc[order, "±95% (pts)"],
                fmt="o", color="#20808D", label="cohorts 2015-17")
    ax.axvline(0, color="k", lw=0.8)
    ax.set_yticks(yy, order)
    ax.set(xlabel="150% bachelor's completion gap, other U.S. minus URM (points)")
    ax.legend(fontsize=8, loc="lower right")
    save("11_equity_gaps")
    """),
    md("""
    Every four-year board graduates URM students at a lower six-year rate than other
    U.S. students. In the 2015-17 cohorts the gap is about 4 to 17 points, and the
    intervals for the small boards (Western, Mines, Adams State) are wide. Between the
    2011-13 and 2015-17 cohorts there is no common direction. Fort Lewis's gap widened
    by about 9 points and Mines's narrowed by about 6. Most other changes are within
    the intervals.

    The comparison is descriptive, not a test of the formula. These cohorts entered
    college before HB 20-1366 took effect, so the funding model cannot have caused
    their gaps. The point is structural: a board can raise its URM share, and its
    funding, while its URM students complete at lower rates, because the formula
    measures who enrolls and how everyone fares, not how the gap changes. The
    graduation-rate metric includes all students, so closing a gap helps only through
    the overall rate. HB 26-1345 adds first-time part-time students to the retention
    rate and widens the transfer credit, but the enacted text
    ([Chapter 391](https://leg.colorado.gov/laws/session-laws/HB26-1345/391/download))
    adds no disaggregated outcome metric. Section 10 models the changes that IPEDS
    can see.
    """),
    md("""
    ## 10. HB 26-1345: what the new definitions change

    HB 26-1345 ([Session Laws chapter 391](https://leg.colorado.gov/laws/session-laws/HB26-1345/391/download)) applies from FY 2027-28. It keeps
    the `D`-ratio arithmetic in sections 2 and 6 word for word, renaming "role and
    mission share" to "previous share", but it changes what four metrics measure and
    where the data come from. The first cell lists each change and whether IPEDS can
    stand in for it.
    """),
    code(r"""
    changes = pd.DataFrame([
        ("Retention adds first-time part-time students", "23-18-302(17)",
         "EF D: RRPTCTA, RET_NMP", "yes: sections 10a-10c"),
        ("Pell-eligible becomes Pell-recipient; concurrent enrollment excluded", "23-18-302(10), (14)",
         "SFA UPGRNTN already counts recipients; no residency or concurrent split", "already the proxy"),
        ("Co-located degree partnership students leave graduation cohorts", "23-18-302(2.5), (8), (9)",
         "none: IPEDS does not flag partnerships", "no"),
        ("Transfer credit after 18 credit hours from any institution", "23-18-302(4)(b)",
         "none: no credit hours or destination at transfer (OM transfer-out is the nearest)", "no"),
        ("Retention and graduation from department data, not IPEDS", "23-18-302(8), (9), (17)",
         "IPEDS becomes proxy-only for every metric", "section 10d (splicing)"),
    ], columns=["change", "C.R.S.", "IPEDS stand-in", "modelled here"]).set_index("change")
    changes
    """),
    md("""
    ### 10a. Inclusive retention

    The new retention rate counts first-time students who start part-time alongside
    those who start full-time. `EF{y}D` reports both cohorts, so the inclusive rate is
    `(RET_NMF + RET_NMP) / (RRFTCTA + RRPTCTA)`. The panel uses the same
    consistent-reporter rule as section 5.
    """),
    code(r"""
    rows = []
    for y in range(2017, 2024):
        ef = load(f"EF{y}D", f"Fall {y}", ["UNITID", "RRFTCTA", "RET_NMF", "RRPTCTA", "RET_NMP"])
        ef = ef.fillna({"RRPTCTA": 0, "RET_NMP": 0})
        rows += [dict(UNITID=r.UNITID, metric="retention_all", year=y, num=r.RET_NMF + r.RET_NMP,
                      den=r.RRFTCTA + r.RRPTCTA, src="") for r in ef.itertuples()]
    inclusive = pd.DataFrame(rows)
    inclusive["board"] = inclusive["UNITID"].map(board_of)

    years = F.formula_window(T, "retention")
    full_time = F.board_series(panel[panel["metric"] == "retention"], years)
    all_starts = F.board_series(inclusive, years)
    D_incl = D.assign(retention=all_starts.apply(F.d_ratio, axis=1))
    print(f"consistent reporters: full-time {F.consistent_reporters(panel[panel['metric'] == 'retention'], years).size}, "
          f"inclusive {F.consistent_reporters(inclusive, years).size}")
    pd.DataFrame({f"full-time {years[-1]} %": full_time[years[-1]] * 100,
                  f"inclusive {years[-1]} %": all_starts[years[-1]] * 100,
                  "level change (pts)": (all_starts[years[-1]] - full_time[years[-1]]) * 100,
                  "D full-time": D["retention"], "D inclusive": D_incl["retention"],
                  "D change": D_incl["retention"] - D["retention"]}).round(4)
    """),
    md("""
    Adding part-time starters lowers measured retention most where they are common:
    by about 4 points at MSU Denver and 6.6 at CCCS in fall 2023, and by about a point
    or less elsewhere. `D` hardly moves, by 0.004 at most, because
    the formula scores each board against its own recent past. A level drop that
    appears in all four years cancels out. What matters is whether part-time retention
    is improving faster or slower than full-time retention.

    ### 10b. Does IPEDS reproduce the fiscal note?

    The [final fiscal note](https://leg.colorado.gov/bill_files/117653/download) applies the part-time change to FY 2025-26 and
    reports the reallocation by board (its Table 1, on a $1,034,081,555 base). The cell
    below applies the IPEDS inclusive `D` to the same year, scales the share changes
    to the fiscal note's base, and compares the two.
    """),
    code(r"""
    FISCAL_NOTE_BASE = 1_034_081_555
    # HB 26-1345 final fiscal note (Aug 26, 2026), Table 1
    fiscal_note = pd.DataFrame({
        "pell_recipient": {"ASU": -104_573, "CCCS": 1_065_232, "CSM": -28_109, "CSU": -391_139, "FLC": -25_350,
                           "CMU": -61_879, "MSU": -103_817, "CU": -576_029, "UNC": -28_841, "WCU": 254_505},
        "part_time": {"ASU": 12_133, "CCCS": 103_945, "CSM": -18_510, "CSU": 19_583, "FLC": -18_136,
                      "CMU": -4_617, "MSU": 4_493, "CU": -55_707, "UNC": -33_623, "WCU": -9_563},
    }).reindex(fund.index)

    base = fund["FY 2024-25"]
    ipeds_pt = (F.step2_shares(base, D_incl) - F.step2_shares(base, D)) * FISCAL_NOTE_BASE
    pt = pd.DataFrame({"IPEDS estimate ($)": ipeds_pt, "fiscal note ($)": fiscal_note["part_time"]})
    agree = int((np.sign(pt.iloc[:, 0]) == np.sign(pt.iloc[:, 1])).sum())
    print(f"correlation {np.corrcoef(pt.iloc[:, 0], pt.iloc[:, 1])[0, 1]:.2f}; signs agree on {agree} of 10 boards; "
          f"moved ${ipeds_pt.clip(lower=0).sum():,.0f} (IPEDS) vs ${fiscal_note['part_time'].clip(lower=0).sum():,.0f} (fiscal note)")
    pt.round(0)
    """),
    md("""
    IPEDS does not reproduce the fiscal note. The estimates correlate negatively with
    it, agree in sign on half the boards, and move less than half as much money. The
    largest disagreement is CCCS: the fiscal note gives it the largest gain, about
    $104,000, while IPEDS gives it a loss. That is the section 5 problem again. The
    CCCS part-time cohort IPEDS reports fell from 1,430 students in fall 2019 to 626 in
    fall 2022, as colleges were reclassified, and the consistent-reporter rule keeps
    only the colleges that were never reclassified. The state counts every college's
    part-time starters in its own data. For the boards IPEDS measures well, both sources
    put the amounts in the tens of thousands of dollars. At that size, modest
    differences between IPEDS and state cohorts can flip the sign.

    The Pell change cannot be tested at all. The fiscal note differences Pell-recipient
    against Pell-eligible allocations, and IPEDS has no Pell-eligible count. The
    recipient-based proxy in section 6 is already measuring roughly what the new law
    asks for.

    ### 10c. CCCS sensitivity: can all thirteen colleges be used?

    The CCCS estimate rests on the six colleges that report a positive retention
    cohort under one definition in every window year. The cell below asks how much
    that choice matters. It recomputes CCCS's full-time and inclusive `D`, and the
    part-time reallocation, under four alternatives, holding every other board at
    its section 10b values:

    - **all 13, pooled as reported**: every college's cohort in every year, so
      colleges enter and leave the pool as IPEDS reclassifies them;
    - **all 13, invisible colleges held flat**: each college without a full window
      keeps its last cohort that was at least a quarter of its fall 2016 size, at the
      same rate, in every window year. This fixes the composition at all thirteen and
      assumes no change at the colleges IPEDS cannot see;
    - **leave one out**: the baseline with each of the six colleges dropped in turn.
    """),
    code(r"""
    cccs_ids = board_of[board_of == "CCCS"].index
    cccs_ft = panel[(panel["metric"] == "retention") & panel["UNITID"].isin(cccs_ids)]
    cccs_in = inclusive[inclusive["UNITID"].isin(cccs_ids)]
    visible = F.consistent_reporters(cccs_in, years)


    def pooled_d(frame):
        g = frame[frame["year"].isin(years)].groupby("year")[["num", "den"]].sum().reindex(years)
        return F.d_ratio(g["num"] / g["den"]), g["den"]


    def held_flat(frame, min_share=0.25):
        parts = [frame[frame["UNITID"].isin(visible) & frame["year"].isin(years)]]
        held = {}
        for u in sorted(set(cccs_ids) - set(visible)):
            q = frame[(frame["UNITID"] == u) & (frame["year"] <= years[-1])].sort_values("year")
            first = q[q["year"] == 2017]["den"].sum()
            q = q[q["den"] >= min_share * first]
            if q.empty or first == 0:
                continue
            last = q.iloc[-1]
            held[instnm[u]] = (int(last["year"]), int(last["den"]))
            parts.append(pd.DataFrame({"UNITID": u, "year": years, "num": last["num"], "den": last["den"]}))
        return pd.concat(parts), held


    def cccs_effect(d_ft, d_in):
        d0 = D.copy()
        d0.loc["CCCS", "retention"] = d_ft
        d1 = D_incl.copy()
        d1.loc["CCCS", "retention"] = d_in
        return (F.step2_shares(base, d1)["CCCS"] - F.step2_shares(base, d0)["CCCS"]) * FISCAL_NOTE_BASE


    variants = {
        "consistent reporters (baseline)": (cccs_ft[cccs_ft["UNITID"].isin(visible)], cccs_in[cccs_in["UNITID"].isin(visible)]),
        "all 13, pooled as reported": (cccs_ft, cccs_in),
    }
    flat_ft, held = held_flat(cccs_ft)
    flat_in, _ = held_flat(cccs_in)
    variants["all 13, invisible colleges held flat"] = (flat_ft, flat_in)
    for u in visible:
        variants[f"drop {instnm[u]}"] = (cccs_ft[cccs_ft["UNITID"].isin(visible.drop(u))],
                                        cccs_in[cccs_in["UNITID"].isin(visible.drop(u))])

    rows = []
    for label, (ft_frame, in_frame) in variants.items():
        d_ft, _ = pooled_d(ft_frame)
        d_in, cohort = pooled_d(in_frame)
        rows.append({"variant": label, "colleges in window": in_frame.loc[in_frame["year"].isin(years) & (in_frame["den"] > 0), "UNITID"].nunique(),
                     "inclusive cohort, newest year": cohort[years[-1]], "D full-time": d_ft,
                     "D inclusive": d_in, "D gap": d_in - d_ft, "CCCS part-time effect ($)": cccs_effect(d_ft, d_in)})
    sensitivity = pd.DataFrame(rows).set_index("variant")
    print("held flat at (year, full-time cohort):", ", ".join(f"{k} ({y}, {n:,})" for k, (y, n) in held.items()))
    loo = sensitivity.filter(like="drop", axis=0)["CCCS part-time effect ($)"]
    print(f"leave-one-out range ${loo.min():,.0f} to ${loo.max():,.0f}; fiscal note ${fiscal_note.loc['CCCS', 'part_time']:,.0f}")
    sensitivity.round(4)
    """),
    code(r"""
    from scipy.optimize import brentq

    d_ft0 = sensitivity.loc["consistent reporters (baseline)", "D full-time"]
    needed = brentq(lambda d: cccs_effect(d_ft0, d) - fiscal_note.loc["CCCS", "part_time"], 0.9, 1.1)

    fall16 = cccs_ft[cccs_ft["year"] == 2017].set_index("UNITID")["den"]
    fall16_pt = cccs_in[cccs_in["year"] == 2017].set_index("UNITID")["den"] - fall16
    print(f"to reproduce the fiscal note, CCCS inclusive D must be {needed:.4f}: "
          f"{needed - d_ft0:+.4f} against full-time D (baseline gap "
          f"{sensitivity.loc['consistent reporters (baseline)', 'D gap']:+.4f})")
    print(f"the six visible colleges were {fall16[visible].sum() / fall16.sum():.0%} of CCCS full-time and "
          f"{fall16_pt[visible].sum() / fall16_pt.sum():.0%} of part-time starters in fall 2016, "
          f"the last year all 13 reported ({fall16.sum():,.0f} and {fall16_pt.sum():,.0f} students)")
    """),
    md("""
    No version of the IPEDS data reproduces the fiscal note. Pooling all thirteen
    colleges as reported adds only three colleges inside the window. Arapahoe's single
    fall 2019 cohort (1,075 starters, 46% retained) lands in the oldest year, and Red
    Rocks and Pueblo contribute a handful of bachelor's seekers. That is enough to flip
    the CCCS estimate from -$46,590 to +$27,810. It is the reclassification artifact
    from section 5 once more: a large, low-retention cohort that appears in the oldest
    year only raises `D` without any change in students' outcomes.

    Holding the seven invisible colleges flat fixes the composition at all thirteen,
    which pulls both `D` ratios toward one (full-time from 1.022 to 1.005). The
    inclusive ratio still sits below the full-time one, so CCCS still loses, about
    $59,500. Dropping one visible college at a time gives anything from -$190,425
    (without Aurora, the largest part-time cohort among the six) to +$32,587. The sign
    of the estimate depends on which single college is included.

    Reproducing the fiscal note's +$103,945 would need CCCS's inclusive `D` to sit
    about 0.003 above its full-time `D`. Every variant here leaves the two within about
    0.001 of each other or puts the inclusive ratio below. The visible colleges were 29%
    of CCCS full-time starters and only 12% of part-time starters in fall 2016, the last
    year all thirteen reported. The state's figure plausibly reflects part-time
    retention trends at the large colleges IPEDS stopped measuring, such as Front
    Range, Pikes Peak, and Red Rocks. That is a question for SURDS, not IPEDS. Within IPEDS, the defensible
    statement is a bound: the data cannot even fix the sign of CCCS's part-time effect.

    ### 10d. The splicing trap

    When the definitions change, the state can recompute all four window years under
    the new rules, or let new-definition years enter the window one at a time. The act
    does not say which. Splicing puts a definitional change into the numerator of `D`
    in the same way IPEDS reclassification does. The cell below compares the two for
    the first year a splice would occur: three full-time-only years plus one inclusive
    year.
    """),
    code(r"""
    spliced = full_time.copy()
    spliced[years[-1]] = all_starts[years[-1]]
    D_splice = D.assign(retention=spliced.apply(F.d_ratio, axis=1))
    splice_dollars = (F.step2_shares(base, D_splice) - F.step2_shares(base, D)) * FISCAL_NOTE_BASE
    splice = pd.DataFrame({"D recomputed": D_incl["retention"], "D spliced": D_splice["retention"],
                           "recomputed ($)": ipeds_pt, "spliced ($)": splice_dollars})
    print(f"moved between boards: recomputed ${ipeds_pt.clip(lower=0).sum():,.0f}, "
          f"spliced ${splice_dollars.clip(lower=0).sum():,.0f}")
    splice.round(4)
    """),
    md("""
    Splicing moves about $984,000 between boards, against $59,000 for a consistent
    recomputation, roughly seventeen times as much. That is almost as much as all eight
    metrics together moved in FY 2025-26 ($1.11 million, section 7). CCCS alone would
    lose about $894,000 and MSU Denver about $90,000, simply because they enrol the
    most part-time students, whose lower retention would read as a decline. CU and CSU
    would gain for the same reason in reverse. None of this would reflect any change in
    students' outcomes. A study of FY 2027-28 should therefore check CDHE's data
    definitions for how the window is built before treating any board's change as
    performance.

    ### 10e. Definitions versus performance

    The fiscal note's two columns can be set beside the performance reallocation from
    section 7.
    """),
    code(r"""
    compare = pd.DataFrame({
        "FY 2025-26 performance": moved["moved"],
        "Pell-recipient switch": fiscal_note["pell_recipient"],
        "part-time retention": fiscal_note["part_time"],
    })
    compare["both definition changes"] = compare["Pell-recipient switch"] + compare["part-time retention"]
    summary = compare.clip(lower=0).sum().rename("moved between boards ($)")
    print(summary.map("{:,.0f}".format).to_string())
    compare.round(0)
    """),
    md("""
    The two definitional changes would move about $1.41 million between boards, more
    than the $1.11 million that a full year of performance moved in FY 2025-26, with no
    change in what students did. Almost all of it comes from the Pell switch
    ($1.32 million), and almost all of it goes to CCCS and Western. The bases differ
    ($1.034 billion in the fiscal note, $1.246 billion here), so the comparison is about
    scale, not exact dollars. The lesson is still clear: in this formula, how a metric
    is defined can matter as much as how institutions perform on it.

    ## Takeaways

    - **The formula is reproducible from public data, roughly.** IPEDS plus CDHE's FTE
      series recover the pattern of FY 2025-26 increases (correlation 0.83), and the
      fit depends on using the documented windows.
    - **It moves little money.** About $1.1 million of $1.25 billion in FY 2025-26, and
      about $1.5 million in the FY 2026-27 request. The incentive at the margin is small.
    - **Performance is relative and front-loaded.** A board gains by improving faster than
      the others, the reward for a lasting gain fades within three years, and the higher
      base persists.
    - **IPEDS cannot see the community colleges correctly.** Reclassification removes most
      of the CCCS retention cohort from IPEDS, which is why the state is moving to SURDS.
    - **Access is rewarded; gaps are not.** Forty percent of the weight rewards enrollment
      shares, and no metric rewards closing completion gaps.
    - **Under HB 26-1345, definitions move as much money as performance.** The fiscal note's
      Pell and part-time changes reallocate about $1.41 million. Splicing old and new
      definitions in one window would move nearly $1 million more, with no change in
      student outcomes.

    ## Exercises

    1. Hold the FY 2025-26 data fixed and change the weights. What weighting would
       have given MSU Denver the smallest increase instead of the largest?
    2. Rebuild `D` using `GR200` (200% graduation) in place of the 150% rate. Which boards
       would gain, and why might a formula prefer the longer window for two-year colleges?
    3. Use `EF{y}C` (residence of first-time students) to restrict the URM proxy to
       Colorado residents. Does the reconstruction improve?
    4. Compute section 9's gaps for Pell recipients with `GR{y}_PELL_SSL`. Is the Pell gap
       larger or smaller than the URM gap on each board?
    5. When the 2024 IPEDS files are published, reconstruct FY 2026-27 and compare it
       with the request's Step 2 adjustments in section 7.
    6. Repeat section 10c with two and three new-definition years in the window. How
       long does a splice keep distorting `D`, and does the distortion change sign?
    7. Section 10c holds the invisible CCCS colleges flat. Replace that assumption with
       each college's own 2017-2019 trend, extrapolated. How far must the invisible
       colleges' part-time retention rise, relative to full-time, to reach the fiscal
       note's +$103,945?
    """),
]
