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
  const sg = v < 0 ? "-" : "";
  if (a >= 1e9) return sg + "$" + (a / 1e9).toFixed(digits ?? 2) + "B";
  if (a >= 1e6) return sg + "$" + (a / 1e6).toFixed(digits ?? 1) + "M";
  return sg + "$" + Math.round(a).toLocaleString("en-US");
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

const state = {
  data: null,
  fin: null,
  board: "ALL",
  dollars: "real",
  unit: null,
  basis: "salaries",
  aud: null,
  audEntity: "cub",
  audView: "per",
  guideStep: 0,
};
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
        ...(fmt ? { callback: fmt } : {}),
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
  const optional = (url) =>
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
  const [data, fin, aud] = await Promise.all([
    fetch("data/colorado.json").then((r) => r.json()),
    optional("data/colorado_finance.json"),
    optional("data/colorado_audited.json"),
  ]);
  state.data = data;
  state.fin = fin;
  state.aud = aud;
  if (fin) setupFinance();
  else document.getElementById("fin").hidden = true;
  if (aud) setupAudited();
  const gjump = document.getElementById("guide-jump");
  gjump.hidden = !aud;
  gjump.addEventListener("click", (e) => {
    e.preventDefault();
    jumpTo("guide", "guide", "#guide-entity");
  });
  const jump = document.getElementById("fin-jump");
  jump.hidden = !fin;
  // #main scrolls internally and the hash holds panel state, so scroll in JS
  // instead of following the anchor.
  jump.addEventListener("click", (e) => {
    e.preventDefault();
    jumpToFinance();
  });
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
  const section = hashGet("section");
  if (fin && section === "finances")
    requestAnimationFrame(() => jumpToFinance(true));
  if (aud && section === "audited" && audVisible())
    requestAnimationFrame(() => jumpTo("aud", "audited", "#aud-entity", true));
  if (aud && section === "guide")
    requestAnimationFrame(() =>
      jumpTo("guide", "guide", "#guide-entity", true),
    );
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
  renderFinance();
  renderAudited();
  renderGuide();
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

/* ── Campus finances (IPEDS F1A) ───────────────────────────────────────── */
const REV_PARTS = [
  { key: "tuition", label: "Net tuition & fees (incl. COF stipend)", color: 0 },
  { key: "state", label: "State grants, contracts & appropriations", color: 1 },
  { key: "local", label: "Local district taxes", color: 2 },
  { key: "federal", label: "Federal student grants (mostly Pell)", color: 4 },
];
const TREND = {
  salaries: [
    { key: "instructionSalaries", label: "Instruction", color: 0 },
    { key: "academicSupportSalaries", label: "Academic support", color: 5 },
    { key: "studentServicesSalaries", label: "Student services", color: 1 },
  ],
  total: [
    { key: "instruction", label: "Instruction", color: 0 },
    { key: "academicSupport", label: "Academic support", color: 5 },
    { key: "studentServices", label: "Student services", color: 1 },
    { key: "institutionalSupport", label: "Institutional support", color: 6 },
  ],
};

function finYears() {
  return state.fin.meta.years;
}
// Finance dollars share the page's FY2025-26 base: IPEDS values are first put
// in FY2023-24 dollars (semiannual Denver CPI), then carried to FY2025-26
// with the same factor the funding charts use.
function finFactor(i) {
  if (state.dollars === "nominal") return 1;
  return state.fin.meta.deflator[i] * state.data.meta.deflator["FY 2023-24"];
}
function finPer(u, key, i) {
  const v = u[key][i];
  const f = u.fte[i];
  return v == null || !f ? null : (v * finFactor(i)) / f;
}
function finUnits() {
  const all = state.fin.units;
  return state.board === "ALL"
    ? all
    : all.filter((u) => u.board === state.board);
}
function finUnit() {
  return state.fin.units.find((u) => u.unitid === state.unit);
}
function shortUnit(n) {
  return n
    .replace("University of Colorado ", "CU ")
    .replace(
      "Colorado State University (Fort Collins, incl. vet med)",
      "CSU Fort Collins",
    )
    .replace("Colorado State University Pueblo", "CSU Pueblo")
    .replace("Metropolitan State University of Denver", "MSU Denver")
    .replace("University of Northern Colorado", "Northern Colorado")
    .replace("Colorado School of Mines", "Mines")
    .replace(" Community College", " CC")
    .replace("Community College of ", "CC of ")
    .replace(" University", "");
}
function coreRevenue(u, i) {
  return REV_PARTS.reduce((s, p) => s + (finPer(u, p.key, i) || 0), 0);
}

function setupFinance() {
  const sel = document.getElementById("fin-unit");
  const boards = state.fin.meta.boards;
  const byBoard = {};
  state.fin.units.forEach((u) =>
    (byBoard[u.board] = byBoard[u.board] || []).push(u),
  );
  sel.innerHTML = Object.keys(byBoard)
    .map(
      (b) =>
        '<optgroup label="' +
        escapeHtml(boards[b]) +
        '">' +
        byBoard[b]
          .map(
            (u) =>
              '<option value="' +
              u.unitid +
              '">' +
              escapeHtml(shortUnit(u.name)) +
              "</option>",
          )
          .join("") +
        "</optgroup>",
    )
    .join("");
  sel.addEventListener("change", () => setUnit(Number(sel.value)));
  document.querySelectorAll("[data-basis]").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.basis = btn.dataset.basis;
      hashSet("basis", state.basis === "salaries" ? null : state.basis);
      renderFinance();
    }),
  );
  const ids = state.fin.units.map((u) => u.unitid);
  const c = Number(hashGet("campus"));
  state.unit = ids.includes(c) ? c : null;
  state.basis = hashGet("basis") === "total" ? "total" : "salaries";
}

function jumpTo(id, section, focusSel, instant) {
  const main = document.getElementById("main");
  const target = document.getElementById(id);
  const top =
    target.getBoundingClientRect().top -
    main.getBoundingClientRect().top +
    main.scrollTop -
    12;
  main.scrollTo({ top, behavior: instant ? "auto" : "smooth" });
  target.querySelector(focusSel).focus({ preventScroll: true });
  hashSet("section", section);
}
function jumpToFinance(instant) {
  jumpTo("fin", "finances", "#fin-unit", instant);
}

function setUnit(id) {
  state.unit = id;
  hashSet("campus", String(id));
  renderFinance();
  // Follow the IPEDS campus into the audited layer when it has a match.
  if (state.aud && AUD_BY_UNIT[id] && AUD_BY_UNIT[id] !== state.audEntity) {
    state.audEntity = AUD_BY_UNIT[id];
    hashSet("aud", state.audEntity);
    renderAudited();
    renderGuide();
  }
}

function renderFinance() {
  if (!state.fin) return;
  const units = finUnits();
  if (!units.some((u) => u.unitid === state.unit)) {
    state.unit = units[0].unitid;
    if (hashGet("campus")) hashSet("campus", String(state.unit));
  }
  document.getElementById("fin-unit").value = String(state.unit);
  document.querySelectorAll("[data-basis]").forEach((btn) => {
    const on = btn.dataset.basis === state.basis;
    btn.classList.toggle("is-on", on);
    btn.setAttribute("aria-checked", on ? "true" : "false");
  });
  const last = finYears().length - 1;
  const yr = shortFy(finYears()[last]);
  const prov = state.fin.meta.provisional.includes(finYears()[last])
    ? " (provisional)"
    : "";
  document.getElementById("fin-sub").textContent =
    selectedLabel() + " · " + units.length + " IPEDS units · " + dollarsLabel();
  document.getElementById("fin-rev-h").textContent =
    "Core revenue per FTE, " + yr + prov;
  renderFinRevenue(units, last);
  renderFinTrend();
  renderFinTable(units, last);
  renderFinFoot();
}

function renderFinRevenue(units, i) {
  destroy("finRev");
  const base = chartBase();
  const rows = units
    .slice()
    .sort((a, b) => coreRevenue(b, i) - coreRevenue(a, i));
  document.getElementById("fin-rev-box").style.height =
    Math.max(12, rows.length * 1.35 + 4) + "rem";
  document.getElementById("fin-rev-legend").innerHTML = legendHtml(
    REV_PARTS.map((p) => ({ label: p.label, color: groupColor(p.color) })),
  );
  const alpha = (u) => (u.unitid === state.unit ? "ff" : "b3");
  charts.finRev = new Chart(document.getElementById("fin-rev"), {
    type: "bar",
    data: {
      labels: rows.map((u) => shortUnit(u.name)),
      datasets: REV_PARTS.map((p) => ({
        label: p.label,
        data: rows.map((u) => finPer(u, p.key, i)),
        backgroundColor: rows.map((u) => groupColor(p.color) + alpha(u)),
        borderColor: css("--color-surface"),
        borderWidth: { right: 1 },
        barPercentage: 0.8,
        categoryPercentage: 0.9,
      })),
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      onClick: (_e, els) => {
        if (!els.length) return;
        const id = rows[els[0].index].unitid;
        setTimeout(() => setUnit(id), 0);
      },
      onHover: (e, els) =>
        (e.native.target.style.cursor = els.length ? "pointer" : "default"),
      plugins: {
        legend: { display: false },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            label: (c) => " " + c.dataset.label + ": " + money(c.parsed.x),
            footer: (items) =>
              "Core total: " + money(coreRevenue(rows[items[0].dataIndex], i)),
          },
        },
      },
      scales: {
        x: axis(
          base,
          "per FTE, " + dollarsLabel(),
          (v) => "$" + v / 1000 + "k",
          {
            stacked: true,
          },
        ),
        y: axis(base, null, undefined, {
          stacked: true,
          grid: { display: false },
          ticks: {
            color: base.text,
            autoSkip: false,
            font: (ctx) => ({
              family: "'Satoshi', sans-serif",
              size: 11,
              weight:
                rows[ctx.index] && rows[ctx.index].unitid === state.unit
                  ? "700"
                  : "400",
            }),
          },
        }),
      },
    },
  });
}

function renderFinTrend() {
  destroy("finTrend");
  const base = chartBase();
  const u = finUnit();
  const parts = TREND[state.basis];
  const labels = finYears().map(shortFy);
  document.getElementById("fin-trend-h").textContent =
    (state.basis === "salaries" ? "Salaries & wages" : "Spending") +
    " per FTE · " +
    shortUnit(u.name);
  document.getElementById("fin-trend-legend").innerHTML = legendHtml(
    parts.map((p) => ({ label: p.label, color: groupColor(p.color) })),
  );
  const last = labels.length - 1;
  charts.finTrend = new Chart(document.getElementById("fin-trend"), {
    type: "line",
    data: {
      labels,
      datasets: parts.map((p) => ({
        label: p.label,
        data: labels.map((_, i) => finPer(u, p.key, i)),
        borderColor: groupColor(p.color),
        backgroundColor: groupColor(p.color),
        borderWidth: p.key.startsWith("instruction") ? 2.5 : 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.25,
        segment: {
          borderDash: (c) =>
            state.fin.meta.provisional.includes(finYears()[c.p1DataIndex])
              ? [4, 3]
              : undefined,
        },
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            label: (c) => " " + c.dataset.label + ": " + money(c.parsed.y),
          },
        },
      },
      scales: {
        x: axis(base, null),
        y: axis(
          base,
          "per FTE, " + dollarsLabel(),
          (v) => "$" + v / 1000 + "k",
          {
            beginAtZero: true,
          },
        ),
      },
    },
  });

  const instrKey = parts[0].key;
  const ssKey = parts[2].key;
  const stat = (label, value, note) =>
    '<div class="dtl__metric"><dt>' +
    label +
    '</dt><dd class="mono">' +
    value +
    "</dd>" +
    (note ? '<dd class="fin__note">' + note + "</dd>" : "") +
    "</div>";
  const chg = (k) => change(finPer(u, k, 0), finPer(u, k, last));
  const fteChg = change(u.fte[0], u.fte[last]);
  document.getElementById("fin-stats").innerHTML =
    stat(
      "FTE " + labels[last],
      int(u.fte[last]),
      pct(fteChg) + " since " + labels[0],
    ) +
    stat(
      "Instruction / FTE",
      money(finPer(u, instrKey, last)),
      pct(chg(instrKey)) + " real since " + labels[0],
    ) +
    stat(
      "Student services / FTE",
      money(finPer(u, ssKey, last)),
      pct(chg(ssKey)) + " real since " + labels[0],
    ) +
    stat(
      "Tuition discount rate",
      u.discountRate[last] == null
        ? "—"
        : (u.discountRate[last] * 100).toFixed(1) + "%",
      "of gross tuition & fees",
    );
}

function renderFinTable(units, i) {
  const basis = state.basis;
  const instr = basis === "salaries" ? "instructionSalaries" : "instruction";
  const ss =
    basis === "salaries" ? "studentServicesSalaries" : "studentServices";
  const y0 = shortFy(finYears()[0]);
  const yN = shortFy(finYears()[i]);
  const what = basis === "salaries" ? " salaries" : "";
  document.querySelector("#fin-table thead").innerHTML =
    "<tr><th>Campus</th><th class='num'>FTE " +
    yN +
    "</th><th class='num'>Core revenue / FTE</th><th class='num'>State share</th><th class='num'>Instruction" +
    what +
    " / FTE</th><th class='num'>Change since " +
    y0 +
    "</th><th class='num'>Student services" +
    what +
    " / FTE</th><th class='num'>Change since " +
    y0 +
    "</th><th class='num'>Discount rate</th></tr>";
  const delta = (v) =>
    v == null
      ? NA
      : Math.abs(v) < 0.0005
        ? "0.0%"
        : '<span class="' +
          (v > 0.005 ? "pos" : v < -0.005 ? "neg" : "") +
          '">' +
          pct(v) +
          "</span>";
  const rows = units
    .slice()
    .sort((a, b) => b.fte[i] - a.fte[i])
    .map((u) => {
      const core = coreRevenue(u, i);
      const st = finPer(u, "state", i);
      return (
        '<tr data-unit="' +
        u.unitid +
        '" tabindex="0"' +
        (u.unitid === state.unit ? ' aria-selected="true"' : "") +
        '><td class="cell-name">' +
        escapeHtml(shortUnit(u.name)) +
        ' <a class="fin__ipeds" data-inst="' +
        u.unitid +
        '" href="index.html#inst=' +
        u.unitid +
        '" title="Open the IPEDS profile">profile</a></td><td class="num mono">' +
        int(u.fte[i]) +
        '</td><td class="num mono">' +
        money(core) +
        '</td><td class="num mono">' +
        (core ? Math.round((st / core) * 100) + "%" : "—") +
        '</td><td class="num mono">' +
        money(finPer(u, instr, i)) +
        '</td><td class="num mono">' +
        delta(change(finPer(u, instr, 0), finPer(u, instr, i))) +
        '</td><td class="num mono">' +
        money(finPer(u, ss, i)) +
        '</td><td class="num mono">' +
        delta(change(finPer(u, ss, 0), finPer(u, ss, i))) +
        '</td><td class="num mono">' +
        (u.discountRate[i] == null
          ? "—"
          : (u.discountRate[i] * 100).toFixed(0) + "%") +
        "</td></tr>"
      );
    })
    .join("");
  const tbody = document.getElementById("fin-tbody");
  tbody.innerHTML = rows;
  tbody.querySelectorAll("tr").forEach((tr) => {
    const pick = (e) => {
      if (e.target.closest("a")) return;
      setUnit(Number(tr.dataset.unit));
    };
    tr.addEventListener("click", pick);
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        pick(e);
      }
    });
  });
  syncLinks();
}

function renderFinFoot() {
  const m = state.fin.meta;
  const prov = m.provisional.length
    ? " " +
      m.provisional.map(shortFy).join(", ") +
      " is provisional (NCES has not yet issued the revised file) and is drawn dashed."
    : "";
  document.getElementById("fin-foot").innerHTML =
    "IPEDS Finance (public institutions, GASB form F1A) with 12-month FTE (undergraduate + graduate) for the same year, " +
    shortFy(m.years[0]) +
    " to " +
    shortFy(m.years[m.years.length - 1]) +
    "." +
    prov +
    " Colorado routes state support through College Opportunity Fund stipends, which campuses book as tuition, and fee-for-service contracts, booked as state grants and contracts, so IPEDS cannot isolate formula funding. " +
    "PERA pension accounting puts large non-cash swings into benefits, so the salaries view is the steadier trend. " +
    "CU Denver | Anschutz and CSU Fort Collins include medical and veterinary schools. Click a bar or row to change campus.";
}

/* ── Audited statements layer (CU and CSU, FY2023-24 and FY2024-25) ───── */
// The boards' own annual financial reports are a year ahead of IPEDS. They
// stay a separate layer: GASB statement lines are not IPEDS F1A lines, so the
// only change shown is between the two years each report carries.
const AUD_REV = [
  { key: "tuitionFeesNet", label: "Net tuition & fees", color: 0 },
  { key: "feeForService", label: "Fee-for-service", color: 1 },
  { key: "grants", label: "Grants & contracts", color: 2 },
  { key: "auxiliaryRevenue", label: "Auxiliary", color: 3 },
  { key: "healthServicesRevenue", label: "Health services", color: 4 },
  { key: "otherRev", label: "Sales & other", color: 6 },
];
const AUD_EXP = [
  ["instruction", "Instruction"],
  ["research", "Research"],
  ["publicService", "Public service"],
  ["academicSupport", "Academic support"],
  ["studentServices", "Student services"],
  ["institutionalSupport", "Institutional support"],
  ["operationMaintenance", "Operation & maintenance"],
  ["scholarships", "Scholarships & aid"],
  ["auxiliaryExpense", "Auxiliary"],
  ["healthServices", "Health services"],
  ["depreciation", "Depreciation"],
  ["otherExpense", "Other"],
];
const AUD_BY_UNIT = {
  126614: "cub",
  126580: "uccs",
  126562: "ucd",
  126818: "csu",
  128106: "csu",
};
const AUD_SHORT = {
  cub: "CU Boulder",
  uccs: "UCCS",
  ucd: "CU Denver | Anschutz",
  cusys: "CU System office",
  cu: "CU (all campuses)",
  csu: "CSU System",
};

function audYears() {
  return state.aud.meta.years;
}
function audEntity(id) {
  return state.aud.entities.find((e) => e.id === (id || state.audEntity));
}
function audFactor(i) {
  if (state.dollars === "nominal") return 1;
  return state.data.meta.deflator[audYears()[i]] || 1;
}
// Value in the page's dollars; "otherRev" is derived.
function audRaw(e, key, i) {
  const v = e.values;
  if (key === "otherRev")
    return (
      v.salesServices[i] + v.otherOperating[i] - v.healthServicesRevenue[i]
    );
  return v[key] ? v[key][i] : null;
}
function audVal(e, key, i, view) {
  const raw = audRaw(e, key, i);
  if (raw == null) return null;
  const d = raw * audFactor(i);
  if ((view || state.audView) === "total") return d;
  const f = e.fte && e.fte[i];
  return f ? d / f : null;
}
function audEntities() {
  const all = state.aud.entities;
  if (state.board === "ALL") return all;
  return all.filter((e) => e.board === state.board);
}
function audVisible() {
  return !!state.aud && (state.board === "ALL" || SPECIALTY.has(state.board));
}

function setupAudited() {
  const opts = (list) =>
    list
      .map(
        (e) =>
          '<option value="' +
          e.id +
          '">' +
          escapeHtml(AUD_SHORT[e.id] || e.name) +
          "</option>",
      )
      .join("");
  const ids = state.aud.entities.map((e) => e.id);
  const h = hashGet("aud");
  state.audEntity = ids.includes(h) ? h : AUD_BY_UNIT[state.unit] || "cub";
  state.audView = hashGet("audview") === "total" ? "total" : "per";
  state.guideStep = 0;

  const sel = document.getElementById("aud-entity");
  sel.addEventListener("change", () => setAudEntity(sel.value));
  sel.dataset.opts = "";
  document.querySelectorAll("[data-aud-view]").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.audView = btn.dataset.audView;
      hashSet("audview", state.audView === "per" ? null : state.audView);
      renderAudited();
    }),
  );
  // The guide skips the system office, which has no students or tuition.
  const gsel = document.getElementById("guide-entity");
  gsel.innerHTML = opts(state.aud.entities.filter((e) => e.fte));
  gsel.addEventListener("change", () => setAudEntity(gsel.value));
  document.getElementById("guide-prev").addEventListener("click", () => {
    setGuideStep(state.guideStep - 1);
  });
  document.getElementById("guide-next").addEventListener("click", () => {
    setGuideStep(state.guideStep + 1);
  });
  document.getElementById("guide-steps").innerHTML = GUIDE_STEPS.map(
    (s, i) =>
      '<li><button class="guide__step" data-step="' +
      i +
      '"><span class="guide__num">' +
      (i + 1) +
      "</span>" +
      escapeHtml(s.pill) +
      "</button></li>",
  ).join("");
  document
    .querySelectorAll(".guide__step")
    .forEach((b) =>
      b.addEventListener("click", () => setGuideStep(Number(b.dataset.step))),
    );
  document.getElementById("guide").hidden = false;
}

function setAudEntity(id) {
  state.audEntity = id;
  hashSet("aud", id);
  renderAudited();
  renderGuide();
}

function renderAudited() {
  const card = document.getElementById("aud");
  if (!state.aud) return;
  card.hidden = !audVisible();
  if (card.hidden) return;
  const list = audEntities();
  const sel = document.getElementById("aud-entity");
  const key = list.map((e) => e.id).join(",");
  if (sel.dataset.opts !== key) {
    sel.innerHTML = list
      .map(
        (e) =>
          '<option value="' +
          e.id +
          '">' +
          escapeHtml(AUD_SHORT[e.id] || e.name) +
          "</option>",
      )
      .join("");
    sel.dataset.opts = key;
  }
  if (!list.some((e) => e.id === state.audEntity)) state.audEntity = list[0].id;
  // Per-FTE is meaningless for the CU system office (no students).
  const e = audEntity();
  if (!e.fte && state.audView === "per") state.audView = "total";
  sel.value = state.audEntity;
  document.querySelectorAll("[data-aud-view]").forEach((btn) => {
    const on = btn.dataset.audView === state.audView;
    btn.classList.toggle("is-on", on);
    btn.setAttribute("aria-checked", on ? "true" : "false");
    btn.disabled = btn.dataset.audView === "per" && !e.fte;
  });
  const yrs = audYears().map(shortFy);
  document.getElementById("aud-year").textContent = yrs[1];
  document.getElementById("aud-sub").textContent =
    (state.board === "ALL" ? "CU and CSU" : state.board) +
    " annual financial reports · " +
    yrs[0] +
    " vs " +
    yrs[1] +
    " · " +
    (state.audView === "per" ? "per FTE, " : "") +
    dollarsLabel();
  const name = AUD_SHORT[e.id] || e.name;
  document.getElementById("aud-rev-h").textContent =
    name + " · operating revenue" + (state.audView === "per" ? " per FTE" : "");
  document.getElementById("aud-exp-h").textContent =
    name +
    " · operating expenses" +
    (state.audView === "per" ? " per FTE" : "");
  document.getElementById("aud-legend").innerHTML = legendHtml([
    { label: yrs[0], color: css("--co-6") },
    { label: yrs[1], color: css("--co-0") },
  ]);
  renderAudBars(
    "audRev",
    "aud-rev",
    "aud-rev-box",
    e,
    AUD_REV.map((p) => [p.key, p.label]),
  );
  renderAudBars("audExp", "aud-exp", "aud-exp-box", e, AUD_EXP);
  renderAudStats(e);
  renderAudTable(list);
  renderAudFoot();
}

function renderAudBars(chartKey, canvasId, boxId, e, parts) {
  destroy(chartKey);
  const base = chartBase();
  const rows = parts.filter(([k]) =>
    [0, 1].some((i) => Math.abs(audRaw(e, k, i) || 0) >= 5e5),
  );
  document.getElementById(boxId).style.height =
    Math.max(9, rows.length * 2.1 + 3) + "rem";
  const per = state.audView === "per";
  const fmt = (v) =>
    per
      ? "$" + (Math.abs(v) >= 1000 ? (v / 1000).toFixed(0) + "k" : v)
      : axisMoney(Math.abs(v)).replace("$", v < 0 ? "−$" : "$");
  charts[chartKey] = new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: {
      labels: rows.map(([, l]) => l),
      datasets: [0, 1].map((i) => ({
        label: shortFy(audYears()[i]),
        data: rows.map(([k]) => audVal(e, k, i)),
        backgroundColor: css(i ? "--co-0" : "--co-6") + (i ? "" : "99"),
        barPercentage: 0.85,
        categoryPercentage: 0.8,
      })),
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            label: (c) =>
              " " +
              c.dataset.label +
              ": " +
              (per
                ? "$" + Math.round(c.parsed.x).toLocaleString("en-US")
                : money(c.parsed.x)),
            footer: (items) => {
              const [k] = rows[items[0].dataIndex];
              const ch = change(audVal(e, k, 0), audVal(e, k, 1));
              return ch == null ? "" : "Change: " + pct(ch);
            },
          },
        },
      },
      scales: {
        x: axis(base, per ? "per FTE" : null, fmt),
        y: axis(base, null, undefined, {
          grid: { display: false },
          ticks: {
            color: base.text,
            autoSkip: false,
            font: { family: "'Satoshi', sans-serif", size: 11 },
          },
        }),
      },
    },
  });
}

function audDelta(a, b) {
  const v = change(a, b);
  if (v == null || !isFinite(v) || a <= 0) return NA;
  if (Math.abs(v) < 0.0005) return "0.0%";
  return (
    '<span class="' +
    (v > 0.005 ? "pos" : v < -0.005 ? "neg" : "") +
    '">' +
    pct(v) +
    "</span>"
  );
}

function audMoney(v) {
  if (v == null) return "—";
  return state.audView === "per" ? money(v) : money(v);
}

function renderAudStats(e) {
  const i = 1;
  const t = (k) => audVal(e, k, i, "total");
  const rev = t("operatingRevenue");
  const gross = t("tuitionFeesGross");
  const disc = gross ? t("allowance") / gross : null;
  const cells = [
    [
      "Operating revenue",
      money(rev),
      audDelta(audVal(e, "operatingRevenue", 0, "total"), rev),
    ],
    [
      "Operating result",
      money(t("operatingIncome")),
      rev ? pct(t("operatingIncome") / rev) + " of revenue" : "",
    ],
    ["Nonoperating, net", money(t("nonoperating")), "Pell " + money(t("pell"))],
    [
      "Tuition discount",
      disc == null ? "—" : Math.round(disc * 100) + "%",
      gross ? "allowance " + money(t("allowance")) : "",
    ],
    [
      "FTE " + shortFy(audYears()[i]),
      e.fte ? int(e.fte[i]) : "—",
      e.fte ? audDelta(e.fte[0], e.fte[1]) + " vs prior" : "no students",
    ],
  ];
  document.getElementById("aud-stats").innerHTML = cells
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
}

function renderAudTable(list) {
  const per = state.audView === "per";
  const yN = shortFy(audYears()[1]);
  const y0 = shortFy(audYears()[0]);
  const cols = [
    ["operatingRevenue", "Operating revenue"],
    ["tuitionFeesNet", "Net tuition & fees"],
    ["operatingExpense", "Operating expenses"],
    ["instruction", "Instruction"],
    ["studentServices", "Student services"],
  ];
  const tail = per ? " / FTE" : "";
  document.querySelector("#aud-table thead").innerHTML =
    "<tr><th>Entity</th><th class='num'>FTE " +
    yN +
    "</th>" +
    cols
      .map(
        ([, l]) =>
          "<th class='num'>" +
          escapeHtml(l) +
          tail +
          "</th><th class='num'>vs " +
          y0 +
          "</th>",
      )
      .join("") +
    "<th class='num'>Pell (total)</th></tr>";
  const rows = list.filter((e) => !per || e.fte);
  document.getElementById("aud-tbody").innerHTML = rows
    .map((e) => {
      const scope =
        e.scope === "campus"
          ? "campus breakout"
          : e.scope === "office"
            ? "system office"
            : e.board === "CSU"
              ? "system, audited"
              : "consolidated, audited";
      return (
        '<tr data-aud="' +
        e.id +
        '" tabindex="0"' +
        (e.id === state.audEntity ? ' aria-selected="true"' : "") +
        '><td class="cell-name">' +
        escapeHtml(AUD_SHORT[e.id] || e.name) +
        '<span class="aud__scope">' +
        scope +
        "</span></td><td class='num mono'>" +
        (e.fte ? int(e.fte[1]) : "—") +
        "</td>" +
        cols
          .map(
            ([k]) =>
              "<td class='num mono'>" +
              audMoney(audVal(e, k, 1)) +
              "</td><td class='num mono'>" +
              audDelta(audVal(e, k, 0), audVal(e, k, 1)) +
              "</td>",
          )
          .join("") +
        "<td class='num mono'>" +
        money(audVal(e, "pell", 1, "total")) +
        "</td></tr>"
      );
    })
    .join("");
  document.querySelectorAll("#aud-tbody tr").forEach((tr) => {
    const pick = () => setAudEntity(tr.dataset.aud);
    tr.addEventListener("click", pick);
    tr.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        pick();
      }
    });
  });
}

function renderAudFoot() {
  const m = state.aud.meta;
  const s = m.sources;
  const recon = (m.reconciliation || []).map(
    (n) => "<li>" + escapeHtml(n) + "</li>",
  );
  document.getElementById("aud-foot").innerHTML =
    "Sources: " +
    link(
      s.csu.url,
      "CSU System audited financial statements, FY2025 (with restated FY2024)",
    ) +
    "; " +
    link(s.cuafr.url, "CU Annual Financial Report, FY2025 (audited)") +
    "; CU campus supplements for " +
    link(s.cu2025.url, "FY2025") +
    " and " +
    link(s.cu2024.url, "FY2024") +
    ". FTE is IPEDS 12-month FTE (EFIA2024, EFIA2025). " +
    "CU campus rows come from CU's unaudited campus supplement, which breaks out the audited totals and reconciles to them; campus operating lines include Denver's internal service centers, which drop out of the consolidated total. " +
    "CSU reports only at system level (Fort Collins, Pueblo, CSU Global, system office), without its foundations. " +
    "These GASB statement lines are not IPEDS F1A lines, so compare years within this card, not against the IPEDS card above. Per-FTE and change figures use " +
    dollarsLabel() +
    "." +
    (recon.length ? "<ul>" + recon.join("") + "</ul>" : "");
}

/* ── How-to-read guide ─────────────────────────────────────────────────── */
const GUIDE_BARS = [
  { label: "Gross tuition & fees", kind: "inc" },
  { label: "Scholarship allowance", kind: "dec" },
  { label: "Net tuition & fees", kind: "total" },
  { label: "Fee-for-service", kind: "inc" },
  { label: "Grants & contracts", kind: "inc" },
  { label: "Auxiliary & other", kind: "inc" },
  { label: "Operating revenue", kind: "total" },
  { label: "Operating expenses", kind: "dec" },
  { label: "Operating result", kind: "total" },
  { label: "Nonoperating, net", kind: "inc" },
  { label: "Capital & other", kind: "inc" },
  { label: "Bottom line", kind: "total" },
];
const GUIDE_STEPS = [
  { pill: "Sticker price", bars: [0, 1, 2] },
  { pill: "Operating revenue", bars: [2, 3, 4, 5, 6] },
  { pill: "Spending", bars: [6, 7] },
  { pill: "Operating loss", bars: [7, 8] },
  { pill: "Nonoperating", bars: [8, 9, 10, 11] },
  { pill: "Compare fairly", bars: [] },
];

function guideEntity() {
  const e = audEntity();
  return e && e.fte ? e : audEntity("cub");
}

// Waterfall geometry: [start, end] per bar, in the page's dollars.
function guideBars(e) {
  const t = (k) => audVal(e, k, 1, "total");
  const gross = t("tuitionFeesGross");
  const net = t("tuitionFeesNet");
  const ffs = t("feeForService");
  const grants = t("grants");
  const rev = t("operatingRevenue");
  const other = rev - net - ffs - grants;
  const exp = t("operatingExpense");
  const op = rev - exp;
  const nonop = t("nonoperating");
  const cap = t("otherRevenues");
  const bottom = op + nonop + cap;
  const spans = [
    [0, gross],
    [net, gross],
    [0, net],
    [net, net + ffs],
    [net + ffs, net + ffs + grants],
    [net + ffs + grants, rev],
    [0, rev],
    [op, rev],
    [Math.min(0, op), Math.max(0, op)],
    [op, op + nonop],
    [op + nonop, bottom],
    [Math.min(0, bottom), Math.max(0, bottom)],
  ];
  const amounts = [
    gross,
    -(gross - net),
    net,
    ffs,
    grants,
    other,
    rev,
    -exp,
    op,
    nonop,
    cap,
    bottom,
  ];
  return {
    spans,
    amounts,
    t,
    gross,
    net,
    ffs,
    grants,
    other,
    rev,
    exp,
    op,
    nonop,
    cap,
    bottom,
  };
}

function setGuideStep(i) {
  state.guideStep = Math.max(0, Math.min(GUIDE_STEPS.length - 1, i));
  renderGuide();
}

const guideLabels = {
  id: "guideLabels",
  afterDatasetsDraw(chart, _a, opts) {
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);
    ctx.save();
    ctx.font = "600 10.5px 'JetBrains Mono', monospace";
    ctx.textBaseline = "middle";
    meta.data.forEach((bar, i) => {
      const a = opts.amounts[i];
      if (a == null) return;
      const on = opts.on(i);
      ctx.fillStyle = on ? opts.text : opts.faint;
      const right = Math.max(bar.x, bar.base);
      const txt = (a < 0 ? "−" : "") + money(Math.abs(a));
      const w = ctx.measureText(txt).width;
      const room = chart.chartArea.right - right;
      if (room > w + 8) {
        ctx.textAlign = "left";
        ctx.fillText(txt, right + 5, bar.y);
      } else {
        ctx.textAlign = "right";
        ctx.fillText(txt, Math.min(bar.x, bar.base) - 5, bar.y);
      }
    });
    ctx.restore();
  },
};

function renderGuide() {
  if (!state.aud) return;
  const e = guideEntity();
  const gsel = document.getElementById("guide-entity");
  gsel.value = e.id;
  const g = guideBars(e);
  const step = GUIDE_STEPS[state.guideStep];
  const on = (i) => !step.bars.length || step.bars.includes(i);
  const system = e.scope === "system";
  GUIDE_BARS[11].label = system ? "Change in net position" : "Before transfers";

  destroy("guide");
  const base = chartBase();
  const color = (kind) =>
    css(kind === "inc" ? "--co-1" : kind === "dec" ? "--co-4" : "--co-6");
  const hex = (c, i) => (on(i) ? c : c + "24");
  document.getElementById("guide-legend").innerHTML = legendHtml([
    { label: "Adds", color: css("--co-1") },
    { label: "Subtracts", color: css("--co-4") },
    { label: "Subtotal", color: css("--co-6") },
  ]);
  charts.guide = new Chart(document.getElementById("guide-chart"), {
    type: "bar",
    data: {
      labels: GUIDE_BARS.map((b) => b.label),
      datasets: [
        {
          data: g.spans,
          backgroundColor: GUIDE_BARS.map((b, i) =>
            hex(
              b.kind === "inc" && g.amounts[i] < 0
                ? color("dec")
                : color(b.kind),
              i,
            ),
          ),
          borderSkipped: false,
          borderRadius: 2,
          barPercentage: 0.78,
          categoryPercentage: 0.92,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 220 },
      layout: { padding: { right: 4 } },
      onClick: (_ev, els) => {
        if (!els.length) return;
        const bar = els[0].index;
        const s = GUIDE_STEPS.findIndex((x) => x.bars.includes(bar));
        if (s >= 0) setTimeout(() => setGuideStep(s), 0);
      },
      onHover: (ev, els) =>
        (ev.native.target.style.cursor = els.length ? "pointer" : "default"),
      plugins: {
        legend: { display: false },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            label: (c) => {
              const a = g.amounts[c.dataIndex];
              return " " + (a < 0 ? "−" : "") + money(Math.abs(a));
            },
          },
        },
        guideLabels: {
          amounts: g.amounts,
          on,
          text: css("--color-text"),
          faint: css("--color-text-faint") || css("--color-text-muted"),
        },
      },
      scales: {
        x: axis(
          base,
          null,
          (v) => axisMoney(Math.abs(v)).replace("$", v < 0 ? "−$" : "$"),
          {
            grace: "12%",
          },
        ),
        y: axis(base, null, undefined, {
          grid: { display: false },
          ticks: {
            autoSkip: false,
            color: (ctx) => (on(ctx.index) ? css("--color-text") : base.text),
            font: (ctx) => ({
              family: "'Satoshi', sans-serif",
              size: 11,
              weight: on(ctx.index) && step.bars.length ? "700" : "400",
            }),
          },
        }),
      },
    },
    plugins: [guideLabels],
  });

  document.querySelectorAll(".guide__step").forEach((b) => {
    const cur = Number(b.dataset.step) === state.guideStep;
    if (cur) b.setAttribute("aria-current", "step");
    else b.removeAttribute("aria-current");
  });
  document.getElementById("guide-prev").disabled = state.guideStep === 0;
  document.getElementById("guide-next").disabled =
    state.guideStep === GUIDE_STEPS.length - 1;
  document.getElementById("guide-count").textContent =
    state.guideStep + 1 + " / " + GUIDE_STEPS.length;
  document.getElementById("guide-body").innerHTML = guideText(e, g);
  const yr = shortFy(audYears()[1]);
  document.getElementById("guide-sub").textContent =
    (AUD_SHORT[e.id] || e.name) + " · " + yr + " · " + dollarsLabel();
  document.getElementById("guide-foot").textContent =
    "Built from the same " +
    yr +
    " statement lines as the audited card. Bars float from where the previous line left off; totals start at zero. " +
    (system
      ? "The bottom line is the statement's change in net position."
      : "Campus figures stop before CU-internal transfers, so the last bar is not the campus's change in net position.");
}

function guideText(e, g) {
  const m = (v) =>
    "<strong>" + (v < 0 ? "−" : "") + money(Math.abs(v)) + "</strong>";
  const name = escapeHtml(AUD_SHORT[e.id] || e.name);
  const t = g.t;
  const i = state.guideStep;
  const perFte = (v) => (e.fte ? money(v / e.fte[1]) : "—");
  if (i === 0) {
    const disc = g.gross ? Math.round(((g.gross - g.net) / g.gross) * 100) : 0;
    return (
      "<h3>1 · Start with the sticker price</h3>" +
      "<p>" +
      name +
      " billed " +
      m(g.gross) +
      " in tuition and fees at published rates. Institutional aid is not shown as spending; it comes off the top as a <strong>scholarship allowance</strong> of " +
      m(g.gross - g.net) +
      ".</p><p>That is a " +
      disc +
      "% discount, leaving " +
      m(g.net) +
      " of net tuition and fees. The net figure is what students, families, and third parties actually paid.</p>"
    );
  }
  if (i === 1) {
    const share = g.rev ? Math.round((g.net / g.rev) * 100) : 0;
    return (
      "<h3>2 · Build operating revenue</h3>" +
      "<p>Add Colorado's <strong>fee-for-service</strong> contracts (" +
      m(g.ffs) +
      "), <strong>grants and contracts</strong> (" +
      m(g.grants) +
      ", mostly sponsored research), and auxiliaries, sales, and other lines (" +
      m(g.other) +
      ") to reach " +
      m(g.rev) +
      " of operating revenue.</p>" +
      "<p>Net tuition is " +
      share +
      "% of it. The College Opportunity Fund stipend the state pays per resident student is already inside tuition, so state support is split between that line and fee-for-service.</p>"
    );
  }
  if (i === 2) {
    const parts = AUD_EXP.map(([k, l]) => [l, t(k)])
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1]);
    const chips = parts
      .slice(0, 6)
      .map(
        ([l, v]) =>
          '<span class="tag">' +
          escapeHtml(l) +
          " " +
          Math.round((v / g.exp) * 100) +
          "%</span>",
      )
      .join("");
    return (
      "<h3>3 · See where the money goes</h3>" +
      "<p>Operating expenses were " +
      m(g.exp) +
      ", reported by <strong>function</strong> (what the spending is for) rather than by object (salaries, supplies).</p>" +
      '<div class="guide__chips">' +
      chips +
      "</div>" +
      "<p>Instruction was " +
      perFte(t("instruction")) +
      " per FTE student. Depreciation is a non-cash charge for using buildings and equipment.</p>"
    );
  }
  if (i === 3) {
    return (
      "<h3>4 · An operating loss is normal</h3>" +
      "<p>Operating revenue minus operating expenses gives an operating result of " +
      m(g.op) +
      (g.rev ? " (" + pct(g.op / g.rev) + " of revenue)" : "") +
      ".</p>" +
      "<p>That is not a warning sign by itself. Under GASB rules for public universities, <strong>Pell grants, gifts, investment income, and state appropriations are nonoperating</strong>, so they fall below this line even though they pay for day-to-day operations.</p>"
    );
  }
  if (i === 4) {
    return (
      "<h3>5 · Nonoperating revenue closes the gap</h3>" +
      "<p>Net nonoperating revenue was " +
      m(g.nonop) +
      ": Pell " +
      m(t("pell")) +
      ", gifts " +
      m(t("gifts")) +
      ", investment income " +
      m(t("investment")) +
      (t("stateAppropriations")
        ? ", state appropriations " + m(t("stateAppropriations"))
        : "") +
      ", less interest on capital debt " +
      m(t("interest")) +
      ".</p>" +
      "<p>Capital appropriations, capital grants and gifts, and similar items add " +
      m(g.cap) +
      ", for a bottom line of " +
      m(g.bottom) +
      (e.scope === "system"
        ? ", the change in net position."
        : ". CU's campus statements continue with internal transfers between campuses and the system office, so this is not the campus's change in net position.") +
      "</p>"
    );
  }
  const fte = e.fte ? int(e.fte[1]) : "—";
  return (
    "<h3>6 · Compare fairly</h3>" +
    "<ul>" +
    "<li><strong>Divide by students.</strong> " +
    name +
    " enrolled " +
    fte +
    " FTE, so operating expenses were " +
    perFte(g.exp) +
    " per FTE.</li>" +
    "<li><strong>Match the scope.</strong> CU Denver | Anschutz includes a medical campus and health services; the CSU figures cover the whole system.</li>" +
    "<li><strong>Don't mix sources.</strong> These GASB statement lines are not IPEDS F1A lines. Compare years within one source.</li>" +
    "<li><strong>Watch pensions.</strong> PERA pension and OPEB accounting move expenses by tens of millions without cash changing hands.</li>" +
    "<li><strong>Restricted money is not flexible.</strong> Research grants and most gifts can only be spent as the donor or sponsor directs.</li>" +
    "</ul>"
  );
}

boot().catch((err) => {
  console.error(err);
  document.querySelector("#loading .loading__text").textContent =
    "Could not load the Colorado panel.";
});
