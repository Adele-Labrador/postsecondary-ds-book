/* ==========================================================================
   IPEDS Explorer — Colorado panel
   Reads data/colorado.json, built by src/ingest/colorado.py from CDHE resident
   FTE reports and Joint Budget Committee staff briefings.
   ========================================================================== */

"use strict";

/* ── Theme (hash-based, shared with the national explorer) ─────────────── */
const SUN =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
const MOON =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

function hashGet(key) {
  const m = new RegExp("(?:^|[#&])" + key + "=([^&]+)").exec(location.hash);
  return m ? decodeURIComponent(m[1]) : null;
}

function hashSet(key, value) {
  const parts = location.hash
    .replace(/^#/, "")
    .split("&")
    .filter((p) => p && !p.startsWith(key + "="));
  if (value != null) parts.push(key + "=" + encodeURIComponent(value));
  history.replaceState(null, "", parts.length ? "#" + parts.join("&") : " ");
  syncLinks();
}

const themeBtn = document.querySelector("[data-theme-toggle]");
let theme =
  hashGet("theme") ||
  (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

function paintTheme() {
  document.documentElement.dataset.theme = theme;
  themeBtn.innerHTML = theme === "dark" ? SUN : MOON;
  themeBtn.setAttribute(
    "aria-label",
    "Switch to " + (theme === "dark" ? "light" : "dark") + " mode",
  );
}
paintTheme();
themeBtn.addEventListener("click", () => {
  theme = theme === "dark" ? "light" : "dark";
  hashSet("theme", theme);
  paintTheme();
  if (state.data) renderAll();
});

// Carry the theme across to the national explorer.
function syncLinks() {
  const t = hashGet("theme");
  for (const id of ["back-link", "home-link"]) {
    const a = document.getElementById(id);
    if (a) a.href = "index.html" + (t ? "#theme=" + t : "");
  }
  document.querySelectorAll("a[data-inst]").forEach((a) => {
    a.href = "index.html#inst=" + a.dataset.inst + (t ? "&theme=" + t : "");
  });
}

/* ── Helpers ───────────────────────────────────────────────────────────── */
const css = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const NA = '<span class="na">—</span>';

function money(v, digits) {
  if (v == null || !isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return "$" + (v / 1e9).toFixed(digits ?? 2) + "B";
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(digits ?? 1) + "M";
  return "$" + Math.round(v).toLocaleString("en-US");
}
const int = (v) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));
function pct(v, digits = 1) {
  if (v == null || !isFinite(v)) return "—";
  const s = (v * 100).toFixed(digits);
  return (v > 0 ? "+" : v < 0 ? "−" : "") + s.replace("-", "") + "%";
}
const change = (a, b) => (a && b != null ? b / a - 1 : null);
const shortFy = (fy) => fy.replace("FY ", "");
function escapeHtml(s) {
  return String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  );
}
const link = (href, text) =>
  '<a href="' + href + '" target="_blank" rel="noopener">' + text + "</a>";

/* ── Groups for the statewide view ─────────────────────────────────────── */
const GROUPS = [
  { id: "CU", label: "CU System", boards: ["CU"] },
  { id: "CSU", label: "CSU System", boards: ["CSU"] },
  { id: "CCCS", label: "Community College System", boards: ["CCCS"] },
  { id: "MSU", label: "MSU Denver", boards: ["MSU"] },
  { id: "UNC", label: "Northern Colorado", boards: ["UNC"] },
  {
    id: "OTHER",
    label: "Other four-year boards",
    boards: ["CMU", "CSM", "FLC", "WCU", "ASU"],
  },
  {
    id: "LOCAL",
    label: "Local district & area technical colleges",
    boards: ["AIMS", "CMC", "ATC"],
  },
];
const IPEDS_LABEL = {
  126562: "CU Denver | Anschutz",
  126818: "CSU Fort Collins",
};
const SPECIALTY = new Set(["CU", "CSU"]);

const state = { data: null, board: "ALL", dollars: "real" };
const charts = {};

/* ── Data access ───────────────────────────────────────────────────────── */
function fy() {
  return state.data.meta.fundingYears;
}
function deflate(values) {
  if (state.dollars === "nominal") return values.slice();
  const d = state.data.meta.deflator;
  return values.map((v, i) => (v == null ? null : v * d[fy()[i]]));
}
function boardsFor(sel) {
  const all = state.data.boards;
  if (sel === "ALL") return all;
  return all.filter((b) => b.id === sel);
}
function sumFunding(boards) {
  return fy().map((_, i) => boards.reduce((s, b) => s + b.funding[i], 0));
}
function fteYears() {
  return state.data.meta.fteYears;
}
function sumFte(boards, key) {
  const n = fteYears().length;
  return Array.from({ length: n }, (_, i) =>
    boards.reduce((s, b) => s + ((b.fte && b.fte[key][i]) || 0), 0),
  );
}
function fteAt(series, fiscalYear) {
  const i = fteYears().indexOf(fiscalYear);
  return i < 0 ? null : series[i];
}
// Funding per resident FTE for a set of boards; area technical colleges are
// dropped because they are not in the resident FTE reports.
function perFte(boards, fiscalYear) {
  const withFte = boards.filter((b) => b.fte);
  const i = fy().indexOf(fiscalYear);
  if (!withFte.length || i < 0) return null;
  const f = deflate(sumFunding(withFte))[i];
  const e = fteAt(sumFte(withFte, "resident"), fiscalYear);
  return e ? f / e : null;
}
function selectedLabel() {
  if (state.board === "ALL") return "All public institutions";
  return state.data.boards.find((b) => b.id === state.board).name;
}
function dollarsLabel() {
  return state.dollars === "real" ? "FY2025-26 dollars" : "nominal dollars";
}

function axisMoney(v) {
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return "$" + Math.round(v / 1e6) + "M";
  return "$" + v;
}

/* ── Chart plumbing ────────────────────────────────────────────────────── */
function chartBase() {
  return {
    text: css("--color-text-muted"),
    grid: css("--grid-line") || css("--color-divider"),
    tooltip: {
      backgroundColor: css("--color-surface-2"),
      titleColor: css("--color-text"),
      bodyColor: css("--color-text-muted"),
      borderColor: css("--color-border"),
      borderWidth: 1,
      padding: 10,
      cornerRadius: 6,
      titleFont: { family: "'Satoshi', sans-serif", size: 12, weight: "700" },
      bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
    },
  };
}
function axis(base, title, fmt, extra) {
  return Object.assign(
    {
      title: title
        ? {
            display: true,
            text: title,
            color: base.text,
            font: { family: "'Satoshi', sans-serif", size: 11, weight: "700" },
          }
        : { display: false },
      grid: { color: base.grid, drawTicks: false },
      border: { display: false },
      ticks: {
        color: base.text,
        font: { family: "'JetBrains Mono', monospace", size: 10 },
        maxRotation: 0,
        autoSkipPadding: 10,
        callback: fmt,
      },
    },
    extra || {},
  );
}
function destroy(key) {
  if (charts[key]) {
    charts[key].destroy();
    delete charts[key];
  }
}

// Draws dashed policy markers between category ticks, labelled at the top.
const markerPlugin = {
  id: "coMarkers",
  afterDatasetsDraw(chart, _args, opts) {
    const marks = opts && opts.marks;
    if (!marks || !marks.length) return;
    const { ctx, chartArea, scales } = chart;
    const x = scales.x;
    const labels = chart.data.labels;
    ctx.save();
    ctx.font = "600 10px 'Satoshi', sans-serif";
    ctx.textBaseline = "top";
    let lastRight = -Infinity;
    let row = 0;
    for (const m of marks) {
      const i = labels.indexOf(shortFy(m.fy));
      if (i < 0) continue;
      const px =
        i === 0
          ? x.getPixelForValue(0)
          : (x.getPixelForValue(i) + x.getPixelForValue(i - 1)) / 2;
      ctx.strokeStyle = css("--color-accent");
      ctx.globalAlpha = 0.85;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(px, chartArea.top);
      ctx.lineTo(px, chartArea.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
      const w = ctx.measureText(m.label).width;
      let tx = px + 4;
      if (tx + w > chartArea.right) tx = px - 4 - w;
      row = tx < lastRight + 6 ? row + 1 : 0;
      lastRight = tx + w;
      ctx.fillStyle = css("--color-accent");
      ctx.globalAlpha = 1;
      ctx.fillText(m.label, tx, chartArea.top + 2 + row * 13);
    }
    ctx.restore();
  },
};

function hatch(color) {
  const c = document.createElement("canvas");
  c.width = c.height = 8;
  const g = c.getContext("2d");
  g.strokeStyle = color;
  g.lineWidth = 2;
  g.beginPath();
  g.moveTo(0, 8);
  g.lineTo(8, 0);
  g.moveTo(-2, 2);
  g.lineTo(2, -2);
  g.moveTo(6, 10);
  g.lineTo(10, 6);
  g.stroke();
  return g.createPattern(c, "repeat");
}

function legendHtml(items) {
  return items
    .map(
      (it) =>
        '<span class="legend__item"><span class="legend__swatch' +
        (it.cls ? " " + it.cls : "") +
        '" style="--sw:' +
        it.color +
        '"></span>' +
        escapeHtml(it.label) +
        "</span>",
    )
    .join("");
}
const groupColor = (i) => css("--co-" + i);

/* ── Boot ──────────────────────────────────────────────────────────────── */
async function boot() {
  state.data = await fetch("data/colorado.json").then((r) => r.json());
  const ids = state.data.boards.map((b) => b.id);
  const b = hashGet("board");
  state.board = ids.includes(b) ? b : "ALL";
  state.dollars = hashGet("dollars") === "nominal" ? "nominal" : "real";

  const sel = document.getElementById("co-board");
  sel.innerHTML =
    '<option value="ALL">All public institutions</option>' +
    state.data.boards
      .map(
        (x) =>
          '<option value="' + x.id + '">' + escapeHtml(x.name) + "</option>",
      )
      .join("");
  sel.value = state.board;
  sel.addEventListener("change", () => setBoard(sel.value));

  document.querySelectorAll("[data-dollars]").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.dollars = btn.dataset.dollars;
      hashSet("dollars", state.dollars === "real" ? null : state.dollars);
      renderAll();
    }),
  );

  renderTimeline();
  renderFoot();
  renderAll();
  syncLinks();
  const loader = document.getElementById("loading");
  loader.classList.add("loading--out");
  setTimeout(() => (loader.hidden = true), 320);
}

function setBoard(id) {
  state.board = id;
  document.getElementById("co-board").value = id;
  hashSet("board", id === "ALL" ? null : id);
  renderAll();
}

function renderAll() {
  document.querySelectorAll("[data-dollars]").forEach((btn) => {
    const on = btn.dataset.dollars === state.dollars;
    btn.classList.toggle("is-on", on);
    btn.setAttribute("aria-checked", on ? "true" : "false");
  });
  renderKpis();
  renderFunding();
  renderFte();
  renderPer();
  renderTable();
}

/* ── KPIs ──────────────────────────────────────────────────────────────── */
function kpi(label, value, delta, note, lowerIsBetter) {
  let cls = "kpi__delta--flat";
  if (delta != null && Math.abs(delta) >= 0.0005) {
    const good = lowerIsBetter ? delta < 0 : delta > 0;
    cls = good ? "kpi__delta--up" : "kpi__delta--down";
  }
  return (
    '<div class="kpi"><span class="kpi__label">' +
    label +
    '</span><span class="kpi__value mono">' +
    value +
    '</span><span class="kpi__delta ' +
    (delta == null ? "kpi__delta--flat" : cls) +
    '">' +
    note +
    "</span></div>"
  );
}

function renderKpis() {
  const boards = boardsFor(state.board);
  const years = fy();
  const f = deflate(sumFunding(boards));
  const last = f.length - 1;
  const first = 0;
  const real = state.dollars === "real";
  const withFte = boards.filter((b) => b.fte);
  const res = sumFte(withFte, "resident");
  const fteNow = fteAt(res, "FY 2024-25");
  const fteBase = fteAt(res, "FY 2019-20");
  let peakI = 0;
  res.forEach((v, i) => (v > res[peakI] ? (peakI = i) : 0));
  const perNow = perFte(boards, "FY 2024-25");
  const perBase = perFte(boards, "FY 2019-20");
  const nominal = sumFunding(boards);
  const cut = change(nominal[0], nominal[1]); // same-year cut: always nominal
  const crf = boards.reduce((s, b) => s + (b.crf || 0), 0);

  const html = [
    kpi(
      "Formula funding, " + shortFy(years[last]),
      money(f[last]),
      change(f[first], f[last]),
      pct(change(f[first], f[last])) +
        " since " +
        shortFy(years[first]) +
        (real ? " (real)" : " (nominal)"),
    ),
    withFte.length
      ? kpi(
          "Resident FTE, 2024-25",
          int(fteNow),
          change(fteBase, fteNow),
          pct(change(fteBase, fteNow)) +
            " since 2019-20 · peak " +
            int(res[peakI]) +
            " in " +
            shortFy(fteYears()[peakI]),
        )
      : kpi(
          "Resident FTE",
          "—",
          null,
          "Area technical colleges report separately",
        ),
    kpi(
      "Per resident FTE, 2024-25",
      money(perNow),
      change(perBase, perNow),
      perNow == null
        ? "No resident FTE series"
        : pct(change(perBase, perNow)) +
            " vs " +
            money(perBase) +
            " in 2019-20",
    ),
    kpi(
      "FY2020-21 cut",
      pct(cut, 0),
      null,
      money(crf, 0) + " federal CRF backfill",
    ),
    kpi(
      "FY2026-27",
      "Flat",
      null,
      "No new state funding; $9.5M GF supplemental cut restored",
    ),
  ];
  document.getElementById("co-kpis").innerHTML = html.join("");
}

/* ── Funding chart ─────────────────────────────────────────────────────── */
function renderFunding() {
  destroy("fund");
  const base = chartBase();
  const years = fy();
  const labels = years.map(shortFy);
  const sets = [];
  const legend = [];
  if (state.board === "ALL") {
    GROUPS.forEach((g, gi) => {
      const members = state.data.boards.filter((b) => g.boards.includes(b.id));
      const color = groupColor(gi);
      sets.push({
        label: g.label,
        data: deflate(sumFunding(members)),
        backgroundColor: color,
        stack: "s",
      });
      legend.push({ label: g.label, color });
    });
  } else {
    const idx = GROUPS.findIndex((g) => g.boards.includes(state.board));
    const color = groupColor(Math.max(0, idx));
    sets.push({
      label: selectedLabel(),
      data: deflate(sumFunding(boardsFor(state.board))),
      backgroundColor: color,
      stack: "s",
    });
    legend.push({ label: selectedLabel(), color });
  }
  const boards = boardsFor(state.board);
  const crf = boards.reduce((s, b) => s + (b.crf || 0), 0);
  const i2021 = years.indexOf("FY 2020-21");
  const crfData = years.map((_, i) => (i === i2021 ? crf : null));
  const accent = css("--color-accent");
  sets.push({
    label: "Federal CRF backfill",
    data: deflate(crfData),
    backgroundColor: hatch(accent),
    borderColor: accent,
    borderWidth: 1,
    stack: "s",
  });
  legend.push({
    label: "Federal CRF backfill (one-time)",
    color: accent,
    cls: "legend__swatch--hatch",
  });

  document.getElementById("fund-legend").innerHTML = legendHtml(legend);
  document.getElementById("fund-sub").textContent =
    selectedLabel() + " · " + dollarsLabel();
  const totals = deflate(sumFunding(boards));
  const marks = state.data.meta.markers.filter(
    (m) => m.kind !== "fte" && labels.includes(shortFy(m.fy)),
  );

  charts.fund = new Chart(document.getElementById("fund"), {
    type: "bar",
    data: { labels, datasets: sets },
    plugins: [markerPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      layout: { padding: { top: 4 } },
      plugins: {
        legend: { display: false },
        coMarkers: { marks },
        tooltip: Object.assign({}, base.tooltip, {
          mode: "index",
          filter: (it) => it.raw != null && it.raw !== 0,
          callbacks: {
            title: (items) => "FY" + items[0].label,
            label: (it) => it.dataset.label + ": " + money(it.raw),
            footer: (items) =>
              "Formula total: " + money(totals[items[0].dataIndex]),
          },
        }),
      },
      scales: {
        x: axis(base, null, undefined, {
          stacked: true,
          grid: { display: false },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            maxRotation: 0,
          },
        }),
        y: axis(base, dollarsLabel(), axisMoney, {
          stacked: true,
          beginAtZero: true,
          grace: "14%",
        }),
      },
    },
  });

  const first = totals[0];
  const last = totals[totals.length - 1];
  const nominal = sumFunding(boards);
  document.getElementById("fund-foot").innerHTML =
    "General Fund for student stipends, fee-for-service contracts, specialty education and local district/area technical college grants — the base the H.B. 20-1366 model allocates. " +
    money(first) +
    " in 2019-20 to " +
    money(last) +
    " in 2025-26 (" +
    pct(change(first, last)) +
    (state.dollars === "real"
      ? "; " + pct(change(nominal[0], nominal[nominal.length - 1])) + " nominal"
      : "") +
    "). One-time funds and the FY2025-26 Auraria Higher Education Center line are excluded.";
}

/* ── Resident FTE chart ────────────────────────────────────────────────── */
function renderFte() {
  destroy("fte");
  const base = chartBase();
  const years = fteYears();
  const labels = years.map(shortFy);
  const sets = [];
  const legend = [];
  const primary = css("--color-primary");
  const muted = css("--color-text-faint");
  const boards = boardsFor(state.board).filter((b) => b.fte);
  const line = (label, data, color, dash, width) => ({
    label,
    data,
    borderColor: color,
    backgroundColor: color,
    borderDash: dash || [],
    borderWidth: width || 2,
    pointRadius: 0,
    pointHoverRadius: 4,
    tension: 0.25,
    spanGaps: false,
  });

  if (!boards.length) {
    document.getElementById("fte-sub").textContent = selectedLabel();
    document.getElementById("fte-legend").innerHTML = "";
    document.getElementById("fte-foot").textContent =
      "Area technical colleges are not in the CDHE resident FTE reports.";
    return;
  }
  const insts = state.data.institutions.filter((d) =>
    boards.some((b) => b.id === d.board),
  );
  if (state.board !== "ALL" && insts.length > 1) {
    sets.push(
      line("Board resident FTE", sumFte(boards, "resident"), primary, [], 2.5),
    );
    legend.push({ label: "Board resident FTE", color: primary });
    insts.forEach((d, i) => {
      const color = css("--co-" + ((i + 1) % 7));
      sets.push(
        line(
          d.name,
          d.resident.map((v) => v || null),
          color,
          [],
          1.5,
        ),
      );
      legend.push({ label: d.name, color });
    });
  } else {
    sets.push(
      line("Resident FTE", sumFte(boards, "resident"), primary, [], 2.5),
    );
    sets.push(
      line(
        "Resident undergraduate",
        sumFte(boards, "residentUg"),
        css("--co-5"),
        [5, 4],
      ),
    );
    sets.push(
      line(
        "All students (incl. nonresident)",
        sumFte(boards, "total"),
        muted,
        [2, 3],
        1.5,
      ),
    );
    legend.push(
      { label: "Resident FTE", color: primary },
      { label: "Resident undergraduate", color: css("--co-5") },
      { label: "All students", color: muted },
    );
  }
  document.getElementById("fte-legend").innerHTML = legendHtml(legend);
  document.getElementById("fte-sub").textContent =
    selectedLabel() + " · state fiscal-year FTE";

  const SHORT = {
    "FY 2015-16": "Grad FTE 24 hrs",
    "FY 2020-21": "COVID",
    "FY 2021-22": "HB 20-1366",
  };
  const marks = state.data.meta.markers
    .filter((m) => labels.includes(shortFy(m.fy)))
    .map((m) => ({ fy: m.fy, label: SHORT[m.fy] || m.label }));
  charts.fte = new Chart(document.getElementById("fte"), {
    type: "line",
    data: { labels, datasets: sets },
    plugins: [markerPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        coMarkers: { marks },
        tooltip: Object.assign({}, base.tooltip, {
          callbacks: {
            title: (items) => "FY" + items[0].label,
            label: (it) => it.dataset.label + ": " + int(it.raw),
          },
        }),
      },
      scales: {
        x: axis(base, null, undefined, {
          grid: { display: false },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 7,
          },
        }),
        y: axis(base, "FTE", (v) => (v >= 1000 ? v / 1000 + "k" : v), {
          grace: "18%",
        }),
      },
    },
  });

  const res = sumFte(boards, "resident");
  const i19 = years.indexOf("FY 2019-20");
  const iLast = years.length - 1;
  document.getElementById("fte-foot").textContent =
    "CDHE resident FTE, July–June fiscal years (30 undergraduate credit hours = 1 FTE; graduate 24 from FY2015-16). " +
    int(res[i19]) +
    " in 2019-20, " +
    int(res[iLast]) +
    " in 2024-25 (" +
    pct(change(res[i19], res[iLast])) +
    "). Not comparable to IPEDS 12-month FTE.";
}

/* ── Per-FTE chart ─────────────────────────────────────────────────────── */
function renderPer() {
  destroy("per");
  const base = chartBase();
  const rows = state.data.boards
    .filter((b) => b.fte)
    .map((b) => ({
      id: b.id,
      name: b.name,
      now: perFte([b], "FY 2024-25"),
      then: perFte([b], "FY 2019-20"),
    }))
    .sort((a, b) => b.now - a.now);
  const all = {
    id: "ALL",
    name: "All public (excl. ATCs)",
    now: perFte(state.data.boards, "FY 2024-25"),
    then: perFte(state.data.boards, "FY 2019-20"),
  };
  rows.push(all);
  const primary = css("--color-primary");
  const ghost = css("--color-surface-offset-2");
  const dim = css("--ramp-2");
  const on = (r) => state.board === "ALL" || r.id === state.board;
  const shortName = (n) =>
    n
      .replace("University of Colorado System", "CU System")
      .replace("Colorado State University System", "CSU System")
      .replace("Colorado Community College System", "CCCS")
      .replace("Metropolitan State University of Denver", "MSU Denver")
      .replace("University of Northern Colorado", "Northern Colorado")
      .replace(" University", "")
      .replace(" Community College", " CC");

  document.getElementById("per-legend").innerHTML = legendHtml([
    { label: "2024-25", color: primary },
    { label: "2019-20", color: ghost },
  ]);
  document.getElementById("per-sub").textContent =
    "Formula funding ÷ resident FTE · " + dollarsLabel();

  charts.per = new Chart(document.getElementById("per"), {
    type: "bar",
    data: {
      labels: rows.map((r) => shortName(r.name)),
      datasets: [
        {
          label: "2024-25",
          data: rows.map((r) => r.now),
          backgroundColor: rows.map((r) =>
            r.id === "ALL" ? css("--color-accent") : on(r) ? primary : dim,
          ),
          barPercentage: 0.9,
          categoryPercentage: 0.8,
        },
        {
          label: "2019-20",
          data: rows.map((r) => r.then),
          backgroundColor: ghost,
          barPercentage: 0.9,
          categoryPercentage: 0.8,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      onClick: (_e, els) => {
        if (!els.length) return;
        const r = rows[els[0].index];
        // Defer: re-rendering destroys this chart mid-event otherwise.
        setTimeout(() => setBoard(r.id === state.board ? "ALL" : r.id), 0);
      },
      plugins: {
        legend: { display: false },
        tooltip: Object.assign({}, base.tooltip, {
          callbacks: {
            label: (it) => it.dataset.label + ": " + money(it.raw),
            afterBody: (items) => {
              const r = rows[items[0].dataIndex];
              const out = [pct(change(r.then, r.now)) + " since 2019-20"];
              if (SPECIALTY.has(r.id))
                out.push("Includes specialty education funding");
              return out;
            },
          },
        }),
      },
      scales: {
        x: axis(base, dollarsLabel(), (v) => "$" + v / 1000 + "k", {
          beginAtZero: true,
        }),
        y: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: base.text,
            font: { family: "'Satoshi', sans-serif", size: 11 },
            autoSkip: false,
          },
        },
      },
    },
  });
  document.getElementById("per-foot").textContent =
    "FY2019-20 uses the pre-cut base. CU and CSU include specialty education (medical school, veterinary medicine, agricultural and forest services), which raises their figures. Click a bar to focus that board.";
}

/* ── Table ─────────────────────────────────────────────────────────────── */
function renderTable() {
  const years = fy();
  const last = years.length - 1;
  const head =
    "<tr><th>Governing board</th><th class='num'>Funding 2025-26</th><th class='num'>Change since 2019-20</th><th class='num'>Resident FTE 2024-25</th><th class='num'>FTE change</th><th class='num'>Per resident FTE 2024-25</th></tr>";
  document.querySelector("#co-table thead").innerHTML = head;
  const rows = state.data.boards.map((b) => {
    const f = deflate(b.funding);
    const res = b.fte ? b.fte.resident : null;
    const fNow = res ? fteAt(res, "FY 2024-25") : null;
    const fThen = res ? fteAt(res, "FY 2019-20") : null;
    const seen = new Map();
    for (const d of state.data.institutions)
      if (d.board === b.id && !seen.has(d.unitid))
        seen.set(d.unitid, IPEDS_LABEL[d.unitid] || d.name);
    const list = [...seen]
      .map(
        ([id, name]) =>
          '<a data-inst="' +
          id +
          '" href="index.html#inst=' +
          id +
          '">' +
          escapeHtml(name) +
          "</a>",
      )
      .join(", ");
    const links =
      seen.size > 3
        ? "<details><summary>" +
          seen.size +
          " institutions</summary>" +
          list +
          "</details>"
        : list;
    const delta = (v) =>
      '<span class="' +
      (v == null ? "" : v >= 0 ? "pos" : "neg") +
      '">' +
      pct(v) +
      "</span>";
    return (
      '<tr data-board="' +
      b.id +
      '"' +
      (b.id === state.board ? ' aria-selected="true"' : "") +
      ' tabindex="0"><td class="cell-name">' +
      escapeHtml(b.name) +
      '<div class="co-links">' +
      (links || '<span class="muted">No resident FTE or IPEDS unit</span>') +
      "</div>" +
      '</td><td class="num mono">' +
      money(f[last]) +
      '</td><td class="num mono">' +
      delta(change(f[0], f[last])) +
      '</td><td class="num mono">' +
      (res ? int(fNow) : NA) +
      '</td><td class="num mono">' +
      (res ? delta(change(fThen, fNow)) : NA) +
      '</td><td class="num mono">' +
      (res ? money(perFte([b], "FY 2024-25")) : NA) +
      "</td></tr>"
    );
  });
  const tbody = document.getElementById("co-tbody");
  tbody.innerHTML = rows.join("");
  tbody.querySelectorAll("tr").forEach((tr) => {
    const pick = (e) => {
      if (e.target.closest("a")) return;
      const id = tr.dataset.board;
      setBoard(id === state.board ? "ALL" : id);
    };
    tr.addEventListener("click", pick);
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        pick(e);
      }
    });
  });
  document.getElementById("table-sub").textContent =
    "Change in " +
    dollarsLabel() +
    ". Click a row to focus the charts; links open the institution in the national explorer.";
  syncLinks();
}

/* ── Timeline & footer ─────────────────────────────────────────────────── */
function renderTimeline() {
  const s = state.data.meta.sources;
  const items = [
    [
      "FY2015-16",
      "Graduate FTE redefined",
      "Graduate FTE switches from 30 to 24 credit hours, lifting graduate-heavy boards in the " +
        link(s.fteReport, "CDHE FTE reports") +
        ".",
    ],
    [
      "FY2020-21",
      "COVID budget cut",
      "General Fund support for institutions cut 58% ($493.2M), with a $450M federal Coronavirus Relief Fund backfill (" +
        link(s.crf, "JBC FY2021-22 briefing") +
        ").",
    ],
    [
      "FY2021-22",
      "H.B. 20-1366 model",
      "First allocation under the three-step model: ongoing additional funding, performance funding on eight metrics, and temporary funding (" +
        link(s.formula, "CDHE funding formula") +
        ").",
    ],
    [
      "Step 2",
      "Performance metrics",
      "Pell share 20%, underrepresented minority share 20%, retention 20%, resident FTE 10%, 100% and 150% graduation 10% each, first-generation headcount 5%, credentials 5% (" +
        link(s.metrics, "CDHE data definitions") +
        ").",
    ],
    [
      "FY2024-25",
      "Largest increase",
      "Formula funding rises 10.9% over FY2023-24, the largest year-over-year increase in the series (" +
        link(
          "https://cdhe.colorado.gov/sites/highered/files/FPA%20October%2018%202024%20Meeting%20Materials.pdf",
          "CDHE funding materials",
        ) +
        ").",
    ],
    [
      "FY2025-26",
      "Mid-year cut",
      "Formula base up 2.5% at enactment, then a $9.5M General Fund supplemental reduction (" +
        link(s.fy2627, "JBC FY2026-27 briefing") +
        ").",
    ],
    [
      "FY2026-27",
      "No new state funding",
      "The Long Bill restores the supplemental cut but adds no state funding; resident tuition capped at 3.5% (5% for CCCS); COF stipend stays $116 per credit hour (" +
        link(
          "https://content.leg.colorado.gov/sites/default/files/26LBNarrativeA.pdf",
          "FY2026-27 Long Bill narrative",
        ) +
        ").",
    ],
    [
      "FY2027-28",
      "H.B. 26-1345",
      "Renames performance funding “results-informed funding”, redefines its metrics and ends the sequential step calculation. Signed June 4, 2026 (" +
        link(s.hb1345, "Colorado General Assembly") +
        ").",
    ],
  ];
  document.getElementById("timeline").innerHTML = items
    .map(
      ([when, title, body]) =>
        '<li class="timeline__item"><span class="timeline__when mono">' +
        when +
        '</span><div><p class="timeline__title">' +
        title +
        '</p><p class="timeline__body">' +
        body +
        "</p></div></li>",
    )
    .join("");
}

function renderFoot() {
  const s = state.data.meta.sources;
  const pages = s.funding
    .map((u, i) => link(u, shortFy(state.data.meta.fundingYears[i])))
    .join(", ");
  document.getElementById("co-foot").innerHTML =
    '<h2 class="foot__title">Sources &amp; method</h2><ul class="foot__list">' +
    "<li><strong>Enrollment.</strong> Resident, resident undergraduate and total FTE from the " +
    link(s.fte, "CDHE FTE Student Enrollment Reports") +
    " (series hed1540, hed1539, hed1538). These are state fiscal-year FTE used by the funding formula, kept separate from the IPEDS figures in the national explorer. Board totals are sums of institutions and can differ from the printed totals by 1–2 FTE of rounding.</li>" +
    "<li><strong>Funding.</strong> Per-board formula base from Joint Budget Committee staff briefings, one table per year: " +
    pages +
    ". FY2020-21 is the FY2019-20 base less the 58% reduction; the federal CRF allocation is shown separately because it was one-time money. Figures exclude financial aid, capital, one-time funds and the FY2025-26 Auraria Higher Education Center line.</li>" +
    "<li><strong>Dollars.</strong> Real values use the " +
    link(s.cpi, "Denver-Aurora-Lakewood CPI-U") +
    " (BLS " +
    escapeHtml(state.data.meta.cpiSeries) +
    ") averaged over July–June fiscal years, expressed in FY2025-26 dollars.</li>" +
    "<li><strong>Per FTE.</strong> Formula funding divided by resident FTE for the same fiscal year. Area technical colleges have no resident FTE series and are left out of per-FTE figures. This is a resource measure, not a cost or efficiency measure.</li>" +
    '<li><strong>Rebuild.</strong> <span class="mono">python -m src.ingest.colorado</span> in ' +
    link(
      "https://github.com/Adele-Labrador/postsecondary-ds-book",
      "the companion repository",
    ) +
    "; built " +
    escapeHtml(state.data.meta.built) +
    ".</li></ul>";
}

boot().catch((err) => {
  console.error(err);
  document.querySelector("#loading .loading__text").textContent =
    "Could not load the Colorado panel.";
});
