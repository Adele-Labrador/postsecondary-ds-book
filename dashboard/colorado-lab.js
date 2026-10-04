/* ==========================================================================
   IPEDS Explorer — Colorado funding formula lab and coverage panel
   Reads data/colorado_formula.json, written by the appendix of
   ipeds-mining/notebooks/11_colorado_performance_funding.ipynb. Loaded before
   colorado.js and called from its boot() and renderAll(); shares its helpers.
   ========================================================================== */

"use strict";

/* ── Formula arithmetic (mirrors ipeds_utils.funding) ──────────────────── */
const LAB_ORDER = [
  "resident_fte",
  "first_gen",
  "credentials",
  "pell_share",
  "urm_share",
  "retention",
  "grad100",
  "grad150",
];
const LAB_SHORT = {
  resident_fte: "Resident FTE",
  first_gen: "First-generation",
  credentials: "Credentials",
  pell_share: "Pell share",
  urm_share: "URM share",
  retention: "Retention",
  grad100: "Graduation 100%",
  grad150: "Graduation 150%",
};
const LAB_COL = {
  resident_fte: "FTE",
  credentials: "Cred.",
  pell_share: "Pell",
  urm_share: "URM",
  retention: "Ret.",
  grad100: "G100",
  grad150: "G150",
};
const LAB_PRESETS = [
  ["cdhe", "CDHE weights", null],
  ["equal", "Equal", Object.fromEntries(LAB_ORDER.map((m) => [m, 12.5]))],
  ["outcomes", "Outcomes only", { retention: 40, grad100: 30, grad150: 30 }],
  ["access", "Access only", { pell_share: 50, urm_share: 50 }],
  ["enrollment", "Enrollment only", { resident_fte: 100 }],
];
const LAB_RET = [
  [
    "ft",
    "Full-time starters",
    "HB 20-1366: the rate CDHE uses today (IPEDS EF D).",
  ],
  [
    "incl",
    "Add part-time, recomputed",
    "HB 26-1345: all four window years rebuilt with part-time starters.",
  ],
  [
    "splice",
    "Add part-time, spliced",
    "Only the newest year uses the new definition. The act does not say which applies.",
  ],
];

const lab = { weights: null, ret: "ft" };

function dRatio(v) {
  if (!v || v.length !== 4 || v.some((x) => x == null)) return NaN;
  const all = (v[0] + v[1] + v[2] + v[3]) / 4;
  return all / ((v[0] + v[1] + v[2]) / 3);
}

function labDefaultWeights() {
  return Object.fromEntries(
    LAB_ORDER.map((m) => [m, Math.round(state.lab.weights[m] * 100)]),
  );
}

function labD(b, m, ret) {
  if (m === "first_gen") return 1; // no IPEDS equivalent: held neutral
  if (m === "retention") {
    if (ret === "incl") return dRatio(b.retentionInclusive);
    if (ret === "splice")
      return dRatio([
        ...b.series.retention.slice(0, 3),
        b.retentionInclusive[3],
      ]);
  }
  return dRatio(b.series[m]);
}

// Step 2 shares for a weight set (any scale) and retention definition.
function labRun(weights, ret) {
  const boards = state.lab.boards;
  const baseSum = boards.reduce((s, b) => s + b.base, 0);
  const pot = boards.reduce((s, b) => s + b.actual, 0);
  const prior = boards.map((b) => b.base / baseSum);
  const total = LAB_ORDER.reduce((s, m) => s + (weights[m] || 0), 0);
  const D = boards.map((b) =>
    Object.fromEntries(LAB_ORDER.map((m) => [m, labD(b, m, ret)])),
  );
  const share = prior.map(() => 0);
  if (total <= 0) prior.forEach((p, i) => (share[i] = p));
  else
    for (const m of LAB_ORDER) {
      const w = (weights[m] || 0) / total;
      if (!w) continue;
      const adj = prior.map((p, i) => p * D[i][m]);
      const sum = adj.reduce((s, x) => s + x, 0);
      adj.forEach((a, i) => (share[i] += (w * a) / sum));
    }
  return boards.map((b, i) => ({
    board: b,
    D: D[i],
    prior: prior[i],
    dollars: share[i] * pot,
    pct: (share[i] * pot) / b.base - 1,
    actualPct: b.actual / b.base - 1,
    moved: share[i] * pot - prior[i] * pot,
  }));
}

function corr(a, b) {
  const n = a.length;
  const ma = a.reduce((s, x) => s + x, 0) / n;
  const mb = b.reduce((s, x) => s + x, 0) / n;
  let sab = 0;
  let saa = 0;
  let sbb = 0;
  for (let i = 0; i < n; i++) {
    sab += (a[i] - ma) * (b[i] - mb);
    saa += (a[i] - ma) ** 2;
    sbb += (b[i] - mb) ** 2;
  }
  return saa && sbb ? sab / Math.sqrt(saa * sbb) : NaN;
}

const signedMoney = (v) =>
  v == null || !isFinite(v)
    ? "—"
    : (v > 0 ? "+" : v < 0 ? "−" : "") + money(Math.abs(v));

/* ── State in the URL hash: lab=10-5-5-20-20-20-10-10~ft ───────────────── */
function labEncode() {
  const w = LAB_ORDER.map((m) => lab.weights[m]).join("-");
  const def = labDefaultWeights();
  const isDefault =
    lab.ret === "ft" && LAB_ORDER.every((m) => lab.weights[m] === def[m]);
  hashSet("lab", isDefault ? null : w + "~" + lab.ret);
}
function labDecode() {
  const raw = hashGet("lab");
  lab.weights = labDefaultWeights();
  lab.ret = "ft";
  if (!raw) return;
  const [w, ret] = raw.split("~");
  const parts = (w || "").split("-").map(Number);
  if (
    parts.length === LAB_ORDER.length &&
    parts.every((x) => x >= 0 && x <= 100)
  )
    LAB_ORDER.forEach((m, i) => (lab.weights[m] = parts[i]));
  if (LAB_RET.some(([k]) => k === ret)) lab.ret = ret;
}

function fidelityTag(m) {
  const f = state.lab.metrics[m].fidelity;
  if (f.startsWith("not available")) return ["Held neutral", "lab__fid--none"];
  if (f.startsWith("proxy")) return ["IPEDS proxy", "lab__fid--proxy"];
  if (f.includes("except")) return ["Same data*", "lab__fid--same"];
  return ["Same data", "lab__fid--same"];
}

/* ── Setup ─────────────────────────────────────────────────────────────── */
function setupLab() {
  labDecode();
  const L = state.lab;
  document.getElementById("lab").hidden = false;
  document.getElementById("cov").hidden = false;
  document.getElementById("lab-fy").textContent = shortFy(L.meta.fiscalYear);

  const wrap = document.getElementById("lab-weights");
  wrap.innerHTML = LAB_ORDER.map((m) => {
    const [tag, cls] = fidelityTag(m);
    return (
      '<div class="lab__w">' +
      '<label class="lab__wlabel" for="lab-w-' +
      m +
      '">' +
      escapeHtml(LAB_SHORT[m]) +
      ' <span class="lab__fid ' +
      cls +
      '">' +
      tag +
      "</span></label>" +
      '<input type="range" min="0" max="50" step="1" id="lab-w-' +
      m +
      '" data-w="' +
      m +
      '" aria-describedby="lab-wv-' +
      m +
      '" />' +
      '<output class="lab__wv mono" id="lab-wv-' +
      m +
      '"></output></div>'
    );
  }).join("");
  wrap.querySelectorAll("input[data-w]").forEach((inp) =>
    inp.addEventListener("input", () => {
      lab.weights[inp.dataset.w] = Number(inp.value);
      labEncode();
      renderLab();
    }),
  );

  document.getElementById("lab-presets").innerHTML = LAB_PRESETS.map(
    ([id, label]) =>
      '<button class="lab__preset" type="button" data-preset="' +
      id +
      '">' +
      label +
      "</button>",
  ).join("");
  document.querySelectorAll("[data-preset]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const p = LAB_PRESETS.find(([id]) => id === btn.dataset.preset)[2];
      lab.weights = p
        ? Object.fromEntries(LAB_ORDER.map((m) => [m, p[m] || 0]))
        : labDefaultWeights();
      labEncode();
      renderLab();
    }),
  );

  document.getElementById("lab-ret").innerHTML = LAB_RET.map(
    ([id, label, note]) =>
      '<label class="lab__radio"><input type="radio" name="lab-ret" value="' +
      id +
      '" /><span><strong>' +
      label +
      "</strong><small>" +
      note +
      "</small></span></label>",
  ).join("");
  document.querySelectorAll('input[name="lab-ret"]').forEach((r) =>
    r.addEventListener("change", () => {
      lab.ret = r.value;
      labEncode();
      renderLab();
    }),
  );

  document.getElementById("lab-reset").addEventListener("click", () => {
    lab.weights = labDefaultWeights();
    lab.ret = "ft";
    labEncode();
    renderLab();
  });
  const copy = document.getElementById("lab-copy");
  copy.addEventListener("click", async () => {
    hashSet("section", "lab");
    let ok = false;
    try {
      await navigator.clipboard.writeText(location.href);
      ok = true;
    } catch (_e) {
      ok = false;
    }
    copy.textContent = ok ? "Link copied" : "Link is in the address bar";
    setTimeout(() => (copy.textContent = "Copy link"), 2200);
  });

  renderReward();
  setupCoverage();
  renderLabFoot();
}

/* ── Render: lab ───────────────────────────────────────────────────────── */
function renderLab() {
  if (!state.lab) return;
  const W = lab.weights;
  const total = LAB_ORDER.reduce((s, m) => s + W[m], 0);
  LAB_ORDER.forEach((m) => {
    document.getElementById("lab-w-" + m).value = W[m];
    const eff = total ? (W[m] / total) * 100 : 0;
    document.getElementById("lab-wv-" + m).innerHTML =
      W[m] +
      (total && Math.abs(total - 100) > 0.01 && W[m]
        ? '<span class="lab__eff"> → ' + eff.toFixed(1) + "%</span>"
        : "");
  });
  document.getElementById("lab-sum").textContent =
    total === 100
      ? "sum 100"
      : total
        ? "sum " + total + ", rescaled to 100"
        : "all zero: prior shares";
  const def = labDefaultWeights();
  const scaled = (w) => {
    const t = LAB_ORDER.reduce((s, m) => s + (w[m] || 0), 0);
    return LAB_ORDER.map((m) => (t ? (w[m] || 0) / t : 0));
  };
  const now = scaled(W);
  document.querySelectorAll("[data-preset]").forEach((btn) => {
    const p = LAB_PRESETS.find(([id]) => id === btn.dataset.preset)[2] || def;
    const on = scaled(p).every((x, i) => Math.abs(x - now[i]) < 1e-9);
    btn.classList.toggle("is-on", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
  document
    .querySelectorAll('input[name="lab-ret"]')
    .forEach((r) => (r.checked = r.value === lab.ret));

  const rows = labRun(W, lab.ret);
  const ref = labRun(def, "ft");
  const actual = rows.map((r) => r.actualPct);
  const model = rows.map((r) => r.pct);
  const r = corr(actual, model);
  const rmse = Math.sqrt(
    rows.reduce((s, x) => s + (x.pct - x.actualPct) ** 2, 0) / rows.length,
  );
  const moved = rows.reduce((s, x) => s + Math.max(x.moved, 0), 0);
  const pot = rows.reduce((t, y) => t + y.board.actual, 0);
  const movedActual = rows.reduce(
    (t, x) => t + Math.max(x.board.actual - x.prior * pot, 0),
    0,
  );
  const vsRef = rows.reduce(
    (s, x, i) => s + Math.max(x.dollars - ref[i].dollars, 0),
    0,
  );
  const spread = [Math.min(...model), Math.max(...model)];
  const cells = [
    [
      "Moved between boards",
      money(moved, 2),
      "vs a uniform increase; actual " + money(movedActual, 2),
    ],
    [
      "Fit to actual " + shortFy(state.lab.meta.fiscalYear),
      isFinite(r) ? "r = " + r.toFixed(2) : "—",
      "RMSE " + (rmse * 100).toFixed(2) + " pts",
    ],
    [
      "Range of increases",
      pct(spread[0], 2) + " to " + pct(spread[1], 2),
      "uniform increase " + pct(uniformPct(), 2),
    ],
    [
      "Moved vs CDHE weights",
      money(vsRef, 2),
      vsRef < 1 ? "same as the formula" : "shifted between boards",
    ],
  ];
  document.getElementById("lab-stats").innerHTML = cells
    .map(
      ([k, v, n]) =>
        "<div><dt>" +
        escapeHtml(k) +
        "</dt><dd>" +
        v +
        (n ? ' <span class="fin__note">' + n + "</span>" : "") +
        "</dd></div>",
    )
    .join("");
  renderLabChart(rows);
  renderLabTable(rows, ref);
}

function uniformPct() {
  const b = state.lab.boards;
  return (
    b.reduce((s, x) => s + x.actual, 0) / b.reduce((s, x) => s + x.base, 0) - 1
  );
}

// Dashed vertical reference line at the uniform increase.
const labUniformPlugin = {
  id: "labUniform",
  afterDatasetsDraw(chart, _a, opts) {
    if (opts == null || opts.value == null) return;
    const { ctx, chartArea, scales } = chart;
    const x = scales.x.getPixelForValue(opts.value);
    ctx.save();
    ctx.strokeStyle = css("--color-accent");
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(x, chartArea.top);
    ctx.lineTo(x, chartArea.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = css("--color-accent");
    ctx.font = "600 10px 'Satoshi', sans-serif";
    ctx.textBaseline = "bottom";
    const label = opts.label;
    const w = ctx.measureText(label).width;
    ctx.fillText(
      label,
      x + 4 + w > chartArea.right ? x - 4 - w : x + 4,
      chartArea.top - 2,
    );
    ctx.restore();
  },
};

function renderLabChart(rows) {
  destroy("lab");
  const base = chartBase();
  const sorted = [...rows].sort((a, b) => b.pct - a.pct);
  const primary = css("--color-primary");
  const text = css("--color-text");
  const u = uniformPct();
  document.getElementById("lab-legend").innerHTML = legendHtml([
    { label: "Modeled increase", color: primary },
    {
      label: "Actual FY2025-26 increase",
      color: text,
      cls: "legend__swatch--dot",
    },
    {
      label: "Uniform increase",
      color: css("--color-accent"),
      cls: "legend__swatch--dash",
    },
  ]);
  charts.lab = new Chart(document.getElementById("lab-chart"), {
    data: {
      labels: sorted.map((x) => x.board.id),
      datasets: [
        {
          type: "bar",
          label: "Modeled",
          data: sorted.map((x) => x.pct * 100),
          backgroundColor: sorted.map((x) =>
            x.pct >= u ? primary : css("--ramp-2"),
          ),
          borderRadius: 3,
          barPercentage: 0.72,
          categoryPercentage: 0.9,
        },
        {
          type: "line",
          label: "Actual",
          data: sorted.map((x) => x.actualPct * 100),
          showLine: false,
          pointStyle: "rectRot",
          pointRadius: 5,
          pointHoverRadius: 7,
          pointBackgroundColor: text,
          pointBorderColor: css("--color-surface"),
          pointBorderWidth: 1.5,
        },
      ],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      animation: { duration: 220 },
      layout: { padding: { top: 14 } },
      plugins: {
        legend: { display: false },
        labUniform: { value: u * 100, label: "uniform " + pct(u, 2) },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            title: (items) => {
              const b = sorted[items[0].dataIndex].board;
              return b.name;
            },
            label: (c) =>
              c.dataset.label +
              " " +
              pct(c.raw / 100, 2) +
              (c.datasetIndex === 0
                ? " · " + signedMoney(sorted[c.dataIndex].moved) + " vs uniform"
                : ""),
          },
        },
      },
      scales: {
        x: axis(
          base,
          "Increase over FY2024-25 (%)",
          (v) => v.toFixed(1) + "%",
          {
            suggestedMin: 0,
          },
        ),
        y: axis(base, null, null, { grid: { display: false } }),
      },
    },
    plugins: [labUniformPlugin],
  });
}

function dCell(d) {
  if (!isFinite(d)) return "<td>" + NA + "</td>";
  const dev = Math.max(-1, Math.min(1, (d - 1) / 0.05));
  const color = dev >= 0 ? "--color-primary" : "--color-error";
  const a = Math.round(Math.abs(dev) * 38);
  return (
    '<td class="lab__d" style="background:color-mix(in oklab, var(' +
    color +
    ") " +
    a +
    '%, transparent)">' +
    d.toFixed(3) +
    "</td>"
  );
}

function renderLabTable(rows, ref) {
  const cols = LAB_ORDER.filter((m) => m !== "first_gen");
  document.querySelector("#lab-table thead").innerHTML =
    '<tr><th>Board</th><th title="Share of FY2024-25 funding">Prior</th>' +
    cols
      .map(
        (m) =>
          '<th title="' +
          escapeHtml(LAB_SHORT[m]) +
          " D ratio" +
          (m === "retention" && lab.ret !== "ft"
            ? ", with part-time starters"
            : "") +
          '">D ' +
          LAB_COL[m] +
          (m === "retention" && lab.ret !== "ft" ? "*" : "") +
          "</th>",
      )
      .join("") +
    '<th>Modeled</th><th>Actual</th><th title="Dollars above or below a uniform increase">$ vs uniform</th><th title="Dollars relative to CDHE weights and full-time retention">vs CDHE</th></tr>';
  const order = rows
    .map((r, i) => [r, ref[i]])
    .sort((a, b) => b[0].pct - a[0].pct);
  document.getElementById("lab-tbody").innerHTML = order
    .map(([r, f]) => {
      const dv = r.dollars - f.dollars;
      return (
        '<tr><td class="cell-name" title="' +
        escapeHtml(r.board.name) +
        '">' +
        r.board.id +
        "</td><td>" +
        (r.prior * 100).toFixed(1) +
        "%</td>" +
        cols.map((m) => dCell(r.D[m])).join("") +
        "<td><strong>" +
        pct(r.pct, 2) +
        "</strong></td><td>" +
        pct(r.actualPct, 2) +
        '</td><td class="' +
        (r.moved >= 0 ? "pos" : "neg") +
        '">' +
        signedMoney(r.moved) +
        '</td><td class="' +
        (Math.abs(dv) < 1 ? "" : dv > 0 ? "pos" : "neg") +
        '">' +
        (Math.abs(dv) < 1 ? "—" : signedMoney(dv)) +
        "</td></tr>"
      );
    })
    .join("");
}

function renderReward() {
  const level = [1, 1, 1, 1.01, 1.01, 1.01, 1.01, 1.01];
  const steps = [0, 1, 2, 3].map((i) => dRatio(level.slice(i, i + 4)) - 1);
  const max = steps[0];
  document.getElementById("lab-reward").innerHTML =
    steps
      .map(
        (s, i) =>
          '<div class="lab__rrow"><span class="mono">Year ' +
          (i + 1) +
          '</span><span class="lab__rbar"><span style="width:' +
          (max ? (s / max) * 100 : 0) +
          '%"></span></span><span class="mono">D ' +
          (s > 1e-12 ? "+" + (s * 100).toFixed(2) + "%" : "±0") +
          "</span></div>",
      )
      .join("") +
    '<p class="lab__rnote">Only the newest year moves <span class="mono">D</span>, by a quarter of its change. Once the gain is in all four window years it is the baseline, and the reward stops. Boards gain by improving faster than other boards.</p>';
}

function renderLabFoot() {
  const s = state.lab.meta.sources;
  const w = state.lab.meta.windows;
  const yrs = (m) => w[m][0] + "–" + w[m][3];
  document.getElementById("lab-foot").innerHTML =
    '<strong>How this works.</strong> For each metric, <span class="mono">D</span> is the four-year average divided by the average of its three oldest years. Each board\'s prior-year share is multiplied by <span class="mono">D</span> and renormalized, and the weighted sum is the Step 2 share (' +
    link(s.definitions, "CDHE data definitions") +
    "). Shares are applied to the actual FY2025-26 total and compared with each board's FY2025-26 appropriation (" +
    link(s.jbcMemo, "JBC staff memo") +
    "). Windows: retention and graduation " +
    yrs("retention") +
    ", URM " +
    yrs("urm_share") +
    ", credentials " +
    yrs("credentials") +
    ", resident FTE " +
    w.resident_fte[0].replace("FY ", "FY") +
    " to " +
    w.resident_fte[3].replace("FY ", "FY") +
    ". The Pell proxy uses " +
    yrs("pell_share") +
    ", one year behind the formula, because the newest SFA file was not yet available when the notebook was built. First-generation status has no IPEDS equivalent and is held neutral: its weight goes to prior shares. Pell, URM and credentials are IPEDS proxies for state records, and the CCCS rates rest on six colleges (see the coverage panel below). Treat results as an approximation of the formula, not CDHE's calculation. The numbers come from " +
    link(
      "https://github.com/Adele-Labrador/postsecondary-ds-book/blob/main/" +
        state.lab.meta.notebook,
      "notebook 11",
    ) +
    ", built " +
    escapeHtml(state.lab.meta.built) +
    ".";
}

/* ── Coverage panel ────────────────────────────────────────────────────── */
const COV_COLS = [
  ["retention", "Retention (full-time)"],
  ["retention_all", "Retention (with part-time)"],
  ["grad100", "Grad. 100%"],
  ["grad150", "Grad. 150%"],
  ["urm_share", "URM share"],
  ["pell_share", "Pell share"],
  ["credentials", "Credentials"],
];
const COV_STATUS = {
  used: ["Used", "cov__s--used"],
  "zero cohort": ["Zero cohort", "cov__s--zero"],
  "definition changed": ["Definition changed", "cov__s--def"],
  "missing year": ["Rate missing", "cov__s--miss"],
  "not reported": ["Not reported", "cov__s--miss"],
};
const HB1345 = {
  resident_fte: "Not changed",
  first_gen: "Not changed",
  credentials:
    "Transfer credit after 18 credit hours from any institution, transfer within the next academic year",
  pell_share:
    "Pell-eligible becomes Pell recipients; concurrent enrollment excluded",
  urm_share: "Not changed",
  retention:
    "Adds first-time part-time starters; department data replaces IPEDS",
  grad100:
    "Co-located degree partnership students excluded; department data replaces IPEDS",
  grad150:
    "Co-located degree partnership students excluded; department data replaces IPEDS",
};
const cov = { board: "CCCS", cohort: "ft" };

function setupCoverage() {
  const L = state.lab;
  const sel = document.getElementById("cov-board");
  sel.innerHTML =
    '<option value="ALL">All boards</option>' +
    L.boards
      .map(
        (b) =>
          '<option value="' + b.id + '">' + escapeHtml(b.name) + "</option>",
      )
      .join("");
  const b = hashGet("covboard");
  if (b === "ALL" || L.boards.some((x) => x.id === b)) cov.board = b;
  sel.value = cov.board;
  sel.addEventListener("change", () => {
    cov.board = sel.value;
    hashSet("covboard", cov.board === "CCCS" ? null : cov.board);
    renderCovMatrix();
  });
  document.querySelectorAll("[data-cov-cohort]").forEach((btn) =>
    btn.addEventListener("click", () => {
      cov.cohort = btn.dataset.covCohort;
      renderCovTrap();
    }),
  );
  renderCovStats();
  renderCovSources();
  renderCovFoot();
}

function cccsUnits() {
  return state.lab.units.filter((u) => u.board === "CCCS");
}

function renderCovStats() {
  const L = state.lab;
  const same = LAB_ORDER.filter((m) =>
    L.metrics[m].fidelity.startsWith("same source"),
  ).reduce((s, m) => s + L.weights[m], 0);
  const sum = (i) => cccsUnits().reduce((s, u) => s + (u.ftCohort[i] || 0), 0);
  const n0 = sum(0);
  const n1 = sum(L.meta.cohortYears.length - 1);
  const c = L.cccs;
  const loo = c.sensitivity.map((r) => r["CCCS part-time effect ($)"]);
  const fn = L.boards.find((b) => b.id === "CCCS").fiscalNote.part_time;
  const cells = [
    [
      "Step 2 weight IPEDS rebuilds",
      Math.round(same * 100) + "%",
      "the rest is SURDS-only; proxies stand in",
    ],
    [
      "CCCS full-time retention cohort",
      int(n0) + " → " + int(n1),
      "fall 2016 to fall 2022 starters, " + pct(n1 / n0 - 1, 0),
    ],
    [
      "CCCS part-time starters IPEDS still sees",
      Math.round(c.visibleSharePt * 100) + "%",
      "of " +
        int(c.fall16Pt) +
        " in fall 2016 (full-time " +
        Math.round(c.visibleShareFt * 100) +
        "%)",
    ],
    [
      "CCCS part-time effect",
      signedMoney(Math.min(...loo)) + " to " + signedMoney(Math.max(...loo)),
      "across samples; fiscal note " + signedMoney(fn),
    ],
  ];
  document.getElementById("cov-stats").innerHTML = cells
    .map(
      ([k, v, n]) =>
        "<div><dt>" +
        escapeHtml(k) +
        "</dt><dd>" +
        v +
        ' <span class="fin__note">' +
        n +
        "</span></dd></div>",
    )
    .join("");
}

function renderCovSources() {
  const L = state.lab;
  const t = document.getElementById("cov-sources");
  t.querySelector("thead").innerHTML =
    "<tr><th>Metric</th><th>Weight</th><th>What the formula uses</th><th>Public stand-in</th><th>Fit</th><th>HB 26-1345, FY2027-28</th></tr>";
  t.querySelector("tbody").innerHTML = LAB_ORDER.map((m) => {
    const [tag, cls] = fidelityTag(m);
    const meta = L.metrics[m];
    return (
      '<tr><td class="cell-name">' +
      escapeHtml(LAB_SHORT[m]) +
      "</td><td>" +
      Math.round(L.weights[m] * 100) +
      '%</td><td class="cov__text">' +
      escapeHtml(meta.cdhe) +
      '</td><td class="cov__text">' +
      escapeHtml(meta.proxy) +
      '</td><td><span class="lab__fid ' +
      cls +
      '">' +
      tag +
      '</span></td><td class="cov__text">' +
      escapeHtml(HB1345[m]) +
      "</td></tr>"
    );
  }).join("");
  document.getElementById("cov-src-note").textContent =
    "* Same IPEDS data except for eight CCCS colleges, whose rates CDHE computes from SURDS. Weights are HB 20-1366's, FY2021-22 to FY2026-27.";
}

function renderCovMatrix() {
  const L = state.lab;
  const units = L.units.filter(
    (u) => cov.board === "ALL" || u.board === cov.board,
  );
  document.getElementById("cov-legend").innerHTML = Object.entries(COV_STATUS)
    .filter(([k]) => k !== "not reported")
    .map(
      ([, [label, cls]]) =>
        '<span class="legend__item"><span class="cov__s ' +
        cls +
        '">' +
        label +
        "</span></span>",
    )
    .join("");
  const t = document.getElementById("cov-matrix");
  const yrs = L.meta.cohortYears;
  t.querySelector("thead").innerHTML =
    "<tr><th>Institution</th>" +
    (cov.board === "ALL" ? "<th>Board</th>" : "") +
    COV_COLS.map(([, l]) => "<th>" + l + "</th>").join("") +
    "<th>Full-time cohort " +
    (yrs[0] - 1) +
    "→" +
    String(yrs[yrs.length - 1] - 1).slice(2) +
    "</th></tr>";
  t.querySelector("tbody").innerHTML = units
    .map((u) => {
      const a = u.ftCohort[0];
      const z = u.ftCohort[u.ftCohort.length - 1];
      return (
        '<tr><td class="cell-name">' +
        escapeHtml(u.name) +
        "</td>" +
        (cov.board === "ALL" ? "<td>" + u.board + "</td>" : "") +
        COV_COLS.map(([k]) => {
          const [label, cls] =
            COV_STATUS[u.status[k]] || COV_STATUS["not reported"];
          return (
            '<td><span class="cov__s ' + cls + '">' + label + "</span></td>"
          );
        }).join("") +
        '<td class="mono">' +
        int(a) +
        " → " +
        int(z) +
        "</td></tr>"
      );
    })
    .join("");
  const used = units.filter((u) => u.status.retention === "used").length;
  document.getElementById("cov-matrix-h").textContent =
    (cov.board === "ALL" ? "All boards" : cov.board) +
    ": " +
    used +
    " of " +
    units.length +
    " institutions usable for retention in the FY2025-26 window";
}

function renderCovTrap() {
  destroy("covTrap");
  document.querySelectorAll("[data-cov-cohort]").forEach((btn) => {
    const on = btn.dataset.covCohort === cov.cohort;
    btn.classList.toggle("is-on", on);
    btn.setAttribute("aria-checked", on ? "true" : "false");
  });
  const L = state.lab;
  const vis = new Set(L.cccs.visible);
  const yrs = L.meta.cohortYears;
  const val = (u, i) =>
    cov.cohort === "ft"
      ? u.ftCohort[i] || 0
      : Math.max((u.allCohort[i] || 0) - (u.ftCohort[i] || 0), 0);
  const sumBy = (pred) =>
    yrs.map((_, i) =>
      cccsUnits()
        .filter(pred)
        .reduce((s, u) => s + val(u, i), 0),
    );
  const base = chartBase();
  const c1 = css("--color-primary");
  const c2 = css("--ramp-2");
  document.getElementById("cov-trap-legend").innerHTML = legendHtml([
    { label: "Six colleges used in the formula window", color: c1 },
    { label: "Seven colleges IPEDS reclassified", color: c2 },
  ]);
  charts.covTrap = new Chart(document.getElementById("cov-trap"), {
    type: "bar",
    data: {
      labels: yrs.map((y) => "Fall " + (y - 1)),
      datasets: [
        {
          label: "Used",
          data: sumBy((u) => vis.has(u.unitid)),
          backgroundColor: c1,
          stack: "s",
        },
        {
          label: "Reclassified",
          data: sumBy((u) => !vis.has(u.unitid)),
          backgroundColor: c2,
          stack: "s",
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      animation: { duration: 200 },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            label: (c) => c.dataset.label + " " + int(c.raw) + " starters",
          },
        },
      },
      scales: {
        x: axis(base, "Starters who entered in", null, {
          stacked: true,
          grid: { display: false },
        }),
        y: axis(base, "Retention cohort", (v) => int(v), { stacked: true }),
      },
    },
  });
}

function sensLabel(v) {
  if (v.startsWith("consistent")) return "Six steady reporters (used)";
  if (v.includes("pooled")) return "All 13, as reported";
  if (v.includes("held flat")) return "All 13, others held flat";
  return v
    .replace("drop ", "Without ")
    .replace("Community College of ", "")
    .replace(" Community College", "")
    .replace(" Junior College", "")
    .replace(" State College", " State")
    .replace(" College", "");
}

function renderCovSens() {
  destroy("covSens");
  const L = state.lab;
  const rows = L.cccs.sensitivity;
  const fn = L.boards.find((b) => b.id === "CCCS").fiscalNote.part_time;
  const base = chartBase();
  const pos = css("--color-success");
  const neg = css("--color-error");
  document.getElementById("cov-sens-legend").innerHTML = legendHtml([
    { label: "CCCS gains", color: pos },
    { label: "CCCS loses", color: neg },
    {
      label: "Fiscal note " + signedMoney(fn),
      color: css("--color-accent"),
      cls: "legend__swatch--dash",
    },
  ]);
  const vals = rows.map((r) => r["CCCS part-time effect ($)"]);
  charts.covSens = new Chart(document.getElementById("cov-sens"), {
    type: "bar",
    data: {
      labels: rows.map((r) => sensLabel(r.variant)),
      datasets: [
        {
          data: vals,
          backgroundColor: vals.map((v) => (v >= 0 ? pos : neg)),
          borderRadius: 3,
          barPercentage: 0.7,
        },
      ],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      animation: { duration: 200 },
      layout: { padding: { top: 14 } },
      plugins: {
        legend: { display: false },
        labUniform: { value: fn, label: "fiscal note" },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            title: (items) => rows[items[0].dataIndex].variant,
            label: (c) => {
              const r = rows[c.dataIndex];
              return [
                signedMoney(c.raw) + " to CCCS",
                "D gap " + (r["D gap"] >= 0 ? "+" : "") + r["D gap"].toFixed(4),
                "newest cohort " + int(r["inclusive cohort, newest year"]),
              ];
            },
          },
        },
      },
      scales: {
        x: axis(
          base,
          "Change in CCCS allocation ($, fiscal-note base)",
          (v) =>
            v === 0
              ? "$0"
              : (v < 0 ? "−" : "") + "$" + Math.abs(v / 1000) + "k",
          { suggestedMax: 120000 },
        ),
        y: axis(base, null, null, { grid: { display: false } }),
      },
    },
    plugins: [labUniformPlugin],
  });
}

function renderCovFoot() {
  const s = state.lab.meta.sources;
  const c = state.lab.cccs;
  document.getElementById("cov-foot").innerHTML =
    "<strong>Why the community colleges disappear.</strong> When a CCCS college starts awarding bachelor's degrees, IPEDS reclassifies it as four-year and counts only bachelor's seekers in its retention cohort, so the cohort drops toward zero without any change in enrollment. The reconstruction keeps an institution only if it reports one definition with a positive cohort in every window year. CDHE computes eight CCCS colleges' rates from SURDS, its student-unit records, and the " +
    link(s.jbcBriefing, "FY2026-27 JBC briefing") +
    " recommends SURDS for all institutions. HB 26-1345 adds part-time starters to retention from FY2027-28 (" +
    link(s.sessionLaw, "Session Laws ch. 391") +
    "). The " +
    link(s.fiscalNote, "final fiscal note") +
    " estimates that change gives CCCS the largest gain. Rebuilt from IPEDS, the CCCS effect changes sign with the sample, and matching the fiscal note would need CCCS's inclusive D to sit " +
    (c.neededGap >= 0 ? "+" : "") +
    c.neededGap.toFixed(4) +
    " above its full-time D, against " +
    c.baselineGap.toFixed(4) +
    " in the data. Only the state's records can settle it. Retention cohorts are from " +
    link(s.ipeds, "IPEDS EF D files") +
    ". Status describes the FY2025-26 window; credentials and enrollment shares are counts, so they survive reclassification.";
}

function renderCoverage() {
  if (!state.lab) return;
  renderCovMatrix();
  renderCovTrap();
  renderCovSens();
}
