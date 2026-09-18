/* ==========================================================================
   IPEDS Explorer — dashboard logic
   Reads the real IPEDS panel built by src/ingest/build_dashboard_data.py and
   the pre-projected state outlines from src/ingest/build_us_map.py.
   ========================================================================== */

"use strict";

/* ── Theme ─────────────────────────────────────────────────────────────── */
const SUN =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
const MOON =
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

const themeBtn = document.querySelector("[data-theme-toggle]");
// Theme choice is kept in the URL hash rather than web storage: the preview
// sandbox blocks web storage, and a hash also makes a chosen theme shareable.
function readThemeFromHash() {
  const m = /(?:^|[#&])theme=(dark|light)\b/.exec(location.hash);
  return m ? m[1] : null;
}

function writeThemeToHash(value) {
  const parts = location.hash
    .replace(/^#/, "")
    .split("&")
    .filter((part) => part && !part.startsWith("theme="));
  parts.push("theme=" + value);
  history.replaceState(null, "", "#" + parts.join("&"));
}

let theme =
  readThemeFromHash() ||
  (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

function paintThemeButton() {
  themeBtn.innerHTML = theme === "dark" ? SUN : MOON;
  themeBtn.setAttribute(
    "aria-label",
    "Switch to " + (theme === "dark" ? "light" : "dark") + " mode",
  );
}

document.documentElement.setAttribute("data-theme", theme);
paintThemeButton();

themeBtn.addEventListener("click", () => {
  theme = theme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
  writeThemeToHash(theme);
  paintThemeButton();
  renderAll();
});

const css = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/* ── Formatting ────────────────────────────────────────────────────────── */
const NA = '<span class="na">—</span>';

const fmt = {
  int: (v) => (v == null ? null : Math.round(v).toLocaleString("en-US")),
  compact: (v) =>
    v == null
      ? null
      : new Intl.NumberFormat("en-US", {
          notation: "compact",
          maximumFractionDigits: 1,
        }).format(v),
  pct: (v) => (v == null ? null : (v * 100).toFixed(0) + "%"),
  pct1: (v) => (v == null ? null : (v * 100).toFixed(1) + "%"),
  ratio: (v) => (v == null ? null : v.toFixed(1) + ":1"),
  usd: (v) => (v == null ? null : "$" + Math.round(v).toLocaleString("en-US")),
  usdK: (v) => (v == null ? null : "$" + Math.round(v / 1000) + "k"),
  signedPct: (v) =>
    v == null ? null : (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%",
};

const or = (s) => (s == null ? NA : s);

/* ── Metric registry ───────────────────────────────────────────────────── */
const METRICS = {
  fte: {
    label: "Undergraduate FTE",
    short: "FTE",
    fmt: fmt.int,
    axis: fmt.compact,
    log: true,
  },
  sfr: {
    label: "Student-to-faculty ratio",
    short: "S:F",
    fmt: fmt.ratio,
    axis: (v) => v,
  },
  gradRate: {
    label: "Graduation rate (150%)",
    short: "Grad 150%",
    fmt: fmt.pct,
    axis: fmt.pct,
  },
  retention: {
    label: "First-year retention",
    short: "Retention",
    fmt: fmt.pct,
    axis: fmt.pct,
  },
  admitRate: {
    label: "Admit rate",
    short: "Admit",
    fmt: fmt.pct,
    axis: fmt.pct,
  },
  yieldRate: {
    label: "Yield rate",
    short: "Yield",
    fmt: fmt.pct,
    axis: fmt.pct,
  },
  pellPct: {
    label: "Pell recipients",
    short: "Pell",
    fmt: fmt.pct,
    axis: fmt.pct,
  },
  pellAvg: {
    label: "Average Pell award",
    short: "Pell $",
    fmt: fmt.usd,
    axis: fmt.usdK,
  },
  tuitionIn: {
    label: "In-state tuition & fees",
    short: "Tuition (in)",
    fmt: fmt.usd,
    axis: fmt.usdK,
  },
  tuitionOut: {
    label: "Out-of-state tuition & fees",
    short: "Tuition (out)",
    fmt: fmt.usd,
    axis: fmt.usdK,
  },
  cagr: {
    label: "Enrollment growth (annualized)",
    short: "Growth",
    fmt: fmt.signedPct,
    axis: fmt.pct1,
  },
};

const CONTROLS = [
  { key: "Public", varName: "--c-public" },
  { key: "Private nonprofit", varName: "--c-nonprofit" },
  { key: "Private for-profit", varName: "--c-forprofit" },
];

const controlColor = (c) => {
  const hit = CONTROLS.find((x) => x.key === c);
  return css(hit ? hit.varName : "--c-other");
};

const RAMP = () => [0, 1, 2, 3, 4, 5].map((i) => css("--ramp-" + i));

/* ── State ─────────────────────────────────────────────────────────────── */
const state = {
  meta: null,
  all: [],
  view: [],
  map: null,
  filters: {
    q: "",
    controls: new Set(),
    families: new Set(),
    state: "",
    minFte: 0,
    require: new Set(),
  },
  axes: { x: "pellPct", y: "gradRate" },
  distMetric: "gradRate",
  mapMetric: "gradRate",
  sort: { key: "fte", dir: -1 },
  limit: 100,
  selected: null,
};

const charts = {};

/* ── Stats helpers ─────────────────────────────────────────────────────── */
function median(values) {
  const a = values.filter((v) => v != null).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = a.length >> 1;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

function mean(a) {
  return a.length ? a.reduce((s, v) => s + v, 0) / a.length : null;
}

function stdev(a) {
  if (a.length < 2) return null;
  const m = mean(a);
  return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / (a.length - 1));
}

/** Ordinary least squares on (x, y) pairs; returns slope/intercept. */
function ols(xs, ys) {
  const n = xs.length;
  const mx = mean(xs);
  const my = mean(ys);
  let num = 0;
  let den = 0;
  for (let i = 0; i < n; i++) {
    num += (xs[i] - mx) * (ys[i] - my);
    den += (xs[i] - mx) ** 2;
  }
  const slope = den === 0 ? 0 : num / den;
  return { slope, intercept: my - slope * mx };
}

/* ── Load ──────────────────────────────────────────────────────────────── */
async function boot() {
  const [panel, map] = await Promise.all([
    fetch("data/institutions.json").then((r) => r.json()),
    fetch("data/us-states.json").then((r) => r.json()),
  ]);

  state.meta = panel.meta;
  state.map = map;
  state.all = panel.institutions.map((d) => {
    const s = d.series;
    // Annualized growth across the reported window, first to last non-null.
    let first = null;
    let firstIdx = 0;
    let last = null;
    let lastIdx = 0;
    for (let i = 0; i < s.length; i++) {
      if (s[i] != null) {
        if (first == null) {
          first = s[i];
          firstIdx = i;
        }
        last = s[i];
        lastIdx = i;
      }
    }
    const span = lastIdx - firstIdx;
    d.cagr =
      first > 0 && last > 0 && span > 0
        ? (last / first) ** (1 / span) - 1
        : null;
    d.complete = s.every((v) => v != null);
    d.searchKey = (
      (d.name || "") +
      " " +
      (d.city || "") +
      " " +
      (d.state || "")
    ).toLowerCase();
    return d;
  });

  buildControls();
  applyFilters();
  renderAll();

  const loader = document.getElementById("loading");
  loader.classList.add("loading--out");
  setTimeout(() => (loader.hidden = true), 320);
}

/* ── Control construction ──────────────────────────────────────────────── */
const REQUIREABLE = [
  ["gradRate", "Grad rate"],
  ["admitRate", "Admit rate"],
  ["retention", "Retention"],
  ["tuitionIn", "Tuition"],
];

function buildControls() {
  const { meta, all } = state;

  document.getElementById("note-total").textContent =
    meta.count.toLocaleString("en-US");
  document.getElementById("note-year").textContent = meta.primaryYear;
  document.getElementById("hdr-year").textContent = meta.primaryYear;
  document.getElementById("foot-year").textContent = meta.primaryYear;
  document.getElementById("foot-aidyear").textContent = meta.aidYear;

  // Control chips with counts
  const controlBox = document.getElementById("f-control");
  CONTROLS.forEach(({ key, varName }) => {
    const n = all.filter((d) => d.control === key).length;
    controlBox.append(
      chip(key, n, () => toggle(state.filters.controls, key), css(varName)),
    );
  });

  // Carnegie family chips
  const families = [
    ...new Set(all.map((d) => d.family).filter(Boolean)),
  ].sort();
  const familyBox = document.getElementById("f-family");
  families.forEach((f) => {
    const n = all.filter((d) => d.family === f).length;
    familyBox.append(chip(f, n, () => toggle(state.filters.families, f)));
  });

  // Require-reported chips
  const reqBox = document.getElementById("f-require");
  REQUIREABLE.forEach(([key, label]) => {
    reqBox.append(chip(label, null, () => toggle(state.filters.require, key)));
  });

  // States
  const stateSel = document.getElementById("f-state");
  const states = [...new Set(all.map((d) => d.state).filter(Boolean))].sort();
  stateSel.append(new Option("All states", ""));
  states.forEach((s) => stateSel.append(new Option(s, s)));
  stateSel.addEventListener("change", () => {
    state.filters.state = stateSel.value;
    refresh();
  });

  // Search (debounced)
  let timer;
  document.getElementById("search").addEventListener("input", (e) => {
    clearTimeout(timer);
    const v = e.target.value;
    timer = setTimeout(() => {
      state.filters.q = v.trim().toLowerCase();
      refresh();
    }, 180);
  });

  // FTE slider — log scale so the low end is usable
  const fteInput = document.getElementById("f-fte");
  const fteOut = document.getElementById("f-fte-out");
  const fteFromSlider = (v) => (v <= 0 ? 0 : Math.round(10 ** Number(v)));
  fteInput.addEventListener("input", () => {
    const v = fteFromSlider(fteInput.value);
    state.filters.minFte = v;
    fteOut.textContent = v.toLocaleString("en-US");
    refresh();
  });

  // Axis / metric selectors
  const axisKeys = Object.keys(METRICS);
  fillSelect("axis-x", axisKeys, state.axes.x, (v) => {
    state.axes.x = v;
    renderScatter();
  });
  fillSelect("axis-y", axisKeys, state.axes.y, (v) => {
    state.axes.y = v;
    renderScatter();
  });
  fillSelect("dist-metric", axisKeys, state.distMetric, (v) => {
    state.distMetric = v;
    renderDist();
  });
  fillSelect("map-metric", axisKeys, state.mapMetric, (v) => {
    state.mapMetric = v;
    renderMap();
  });

  document.getElementById("reset").addEventListener("click", resetFilters);
  document.getElementById("export").addEventListener("click", exportCsv);
  document.getElementById("more").addEventListener("click", () => {
    state.limit += 100;
    renderTable();
  });

  // Mobile sidebar
  const sidebar = document.getElementById("sidebar");
  const sidebarScrim = document.getElementById("sidebar-scrim");

  function setSidebar(open) {
    sidebar.classList.toggle("is-open", open);
    sidebarScrim.hidden = !open;
  }

  document.getElementById("menu").addEventListener("click", () => {
    setSidebar(!sidebar.classList.contains("is-open"));
  });
  sidebarScrim.addEventListener("click", () => setSidebar(false));
  document
    .getElementById("main")
    .addEventListener("click", () => setSidebar(false));
  // The panel is off-canvas only below the breakpoint; if the window grows while
  // it is open, drop the overlay so it does not linger over the docked sidebar.
  matchMedia("(min-width: 900px)").addEventListener("change", (e) => {
    if (e.matches) setSidebar(false);
  });

  // Drawer dismissal
  document.getElementById("scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    closeDrawer();
    setSidebar(false);
  });
}

function chip(label, count, onToggle, dotColor) {
  const b = document.createElement("button");
  b.className = "chip";
  b.type = "button";
  b.setAttribute("aria-pressed", "false");
  if (dotColor) {
    const dot = document.createElement("span");
    dot.className = "chip__dot";
    dot.style.setProperty("--dot", dotColor);
    b.append(dot);
  }
  const text = document.createElement("span");
  text.textContent = label;
  b.append(text);
  if (count != null) {
    const n = document.createElement("span");
    n.className = "chip__n";
    n.textContent = count.toLocaleString("en-US");
    b.append(n);
  }
  b.addEventListener("click", () => {
    const next = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", String(next));
    onToggle();
    refresh();
  });
  return b;
}

function toggle(set, value) {
  if (set.has(value)) set.delete(value);
  else set.add(value);
}

function fillSelect(id, keys, current, onChange) {
  const el = document.getElementById(id);
  keys.forEach((k) => el.append(new Option(METRICS[k].label, k)));
  el.value = current;
  el.addEventListener("change", () => onChange(el.value));
}

function resetFilters() {
  state.filters = {
    q: "",
    controls: new Set(),
    families: new Set(),
    state: "",
    minFte: 0,
    require: new Set(),
  };
  document.getElementById("search").value = "";
  document.getElementById("f-state").value = "";
  document.getElementById("f-fte").value = 0;
  document.getElementById("f-fte-out").textContent = "0";
  document
    .querySelectorAll('.chip[aria-pressed="true"]')
    .forEach((c) => c.setAttribute("aria-pressed", "false"));
  refresh();
}

/* ── Filtering ─────────────────────────────────────────────────────────── */
function applyFilters() {
  const f = state.filters;
  state.view = state.all.filter((d) => {
    if (f.q && !d.searchKey.includes(f.q)) return false;
    if (f.controls.size && !f.controls.has(d.control)) return false;
    if (f.families.size && !f.families.has(d.family)) return false;
    if (f.state && d.state !== f.state) return false;
    if (f.minFte && (d.fte || 0) < f.minFte) return false;
    for (const key of f.require) if (d[key] == null) return false;
    return true;
  });
  state.limit = 100;
}

function refresh() {
  applyFilters();
  renderAll();
}

function renderAll() {
  renderChips();
  renderKpis();
  renderScatter();
  renderTrend();
  renderDist();
  renderMap();
  renderTable();
  if (state.selected) openDrawer(state.selected, true);
}

/* ── Active filter chips ───────────────────────────────────────────────── */
function renderChips() {
  const box = document.getElementById("active-chips");
  const f = state.filters;
  box.textContent = "";

  const items = [];
  if (f.q) items.push(['Search: "' + f.q + '"', () => (f.q = "")]);
  f.controls.forEach((c) => items.push([c, () => f.controls.delete(c)]));
  f.families.forEach((c) => items.push([c, () => f.families.delete(c)]));
  if (f.state) items.push(["State: " + f.state, () => (f.state = "")]);
  if (f.minFte)
    items.push([
      "FTE ≥ " + f.minFte.toLocaleString("en-US"),
      () => (f.minFte = 0),
    ]);
  f.require.forEach((k) =>
    items.push(["Reports " + METRICS[k].short, () => f.require.delete(k)]),
  );

  if (!items.length) {
    const t = document.createElement("span");
    t.className = "tag";
    t.textContent = "All institutions";
    box.append(t);
    return;
  }

  items.slice(0, 6).forEach(([label, clear]) => {
    const t = document.createElement("span");
    t.className = "tag";
    t.append(document.createTextNode(label));
    const x = document.createElement("button");
    x.type = "button";
    x.textContent = "×";
    x.setAttribute("aria-label", "Remove filter " + label);
    x.addEventListener("click", () => {
      clear();
      syncChipButtons();
      refresh();
    });
    t.append(x);
    box.append(t);
  });

  if (items.length > 6) {
    const t = document.createElement("span");
    t.className = "tag";
    t.textContent = "+" + (items.length - 6) + " more";
    box.append(t);
  }
}

/** Re-sync sidebar chip pressed states after a chip is cleared from the header. */
function syncChipButtons() {
  const f = state.filters;
  const label = (btn) =>
    btn.querySelector("span:not(.chip__dot):not(.chip__n)").textContent;
  document.querySelectorAll("#f-control .chip").forEach((b) => {
    b.setAttribute("aria-pressed", String(f.controls.has(label(b))));
  });
  document.querySelectorAll("#f-family .chip").forEach((b) => {
    b.setAttribute("aria-pressed", String(f.families.has(label(b))));
  });
  document.querySelectorAll("#f-require .chip").forEach((b) => {
    const key = (REQUIREABLE.find(([, l]) => l === label(b)) || [])[0];
    b.setAttribute("aria-pressed", String(f.require.has(key)));
  });
  document.getElementById("f-state").value = f.state;
  document.getElementById("search").value = f.q;
  if (!f.minFte) {
    document.getElementById("f-fte").value = 0;
    document.getElementById("f-fte-out").textContent = "0";
  }
}

/* ── KPIs ──────────────────────────────────────────────────────────────── */
function renderKpis() {
  const { view, all } = state;
  const box = document.getElementById("kpis");

  document.getElementById("note-count").textContent =
    view.length.toLocaleString("en-US");
  document.getElementById("hdr-count").textContent =
    view.length.toLocaleString("en-US");

  const totalFte = view.reduce((s, d) => s + (d.fte || 0), 0);
  const allFte = all.reduce((s, d) => s + (d.fte || 0), 0);

  const cards = [
    {
      label: "Institutions",
      value: view.length.toLocaleString("en-US"),
      note: ((view.length / all.length) * 100).toFixed(1) + "% of universe",
      tone: "flat",
    },
    {
      label: "Undergrad FTE",
      value: fmt.compact(totalFte),
      note: ((totalFte / allFte) * 100).toFixed(1) + "% of national FTE",
      tone: "flat",
    },
    metricCard("Median grad rate", "gradRate"),
    metricCard("Median S:F ratio", "sfr", true),
    metricCard("Median Pell share", "pellPct"),
  ];

  box.textContent = "";
  cards.forEach((c) => {
    const el = document.createElement("article");
    el.className = "kpi";
    el.innerHTML =
      '<span class="kpi__label">' +
      c.label +
      '</span><span class="kpi__value">' +
      (c.value == null ? "—" : c.value) +
      '</span><span class="kpi__delta kpi__delta--' +
      c.tone +
      '">' +
      c.note +
      "</span>";
    box.append(el);
  });
}

/** KPI card comparing the filtered median against the national median. */
function metricCard(label, key, lowerIsBetter) {
  const m = METRICS[key];
  const viewMed = median(state.view.map((d) => d[key]));
  const allMed = median(state.all.map((d) => d[key]));
  const n = state.view.filter((d) => d[key] != null).length;

  if (viewMed == null) {
    return { label, value: null, note: "not reported in view", tone: "flat" };
  }

  const diff = viewMed - allMed;
  const rel = allMed ? diff / allMed : 0;
  let tone = "flat";
  if (Math.abs(rel) >= 0.01) {
    const better = lowerIsBetter ? diff < 0 : diff > 0;
    tone = better ? "up" : "down";
  }
  const arrow = Math.abs(rel) < 0.01 ? "" : diff > 0 ? "▲ " : "▼ ";
  const note =
    arrow +
    (Math.abs(rel) < 0.01 ? "at" : Math.abs(rel * 100).toFixed(0) + "% vs") +
    " national " +
    m.fmt(allMed) +
    " · n=" +
    n.toLocaleString("en-US");

  return { label, value: m.fmt(viewMed), note, tone };
}

/* ── Chart defaults ────────────────────────────────────────────────────── */
function isDark() {
  const set = document.documentElement.dataset.theme;
  if (set) return set === "dark";
  // No explicit choice yet: the stylesheet falls back to prefers-color-scheme.
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function chartBase() {
  const text = css("--color-text-muted");
  const grid = css("--grid-line");
  return {
    responsive: true,
    maintainAspectRatio: false,
    font: { family: "'Satoshi', sans-serif" },
    text,
    grid,
    tooltip: {
      backgroundColor: css("--color-surface-2"),
      titleColor: css("--color-text"),
      bodyColor: css("--color-text-muted"),
      borderColor: css("--color-border"),
      borderWidth: 1,
      padding: 10,
      cornerRadius: 6,
      displayColors: false,
      titleFont: { family: "'Satoshi', sans-serif", size: 12, weight: "700" },
      bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
    },
  };
}

function axisConf(base, metric, titleText) {
  const m = METRICS[metric];
  return {
    type: m.log ? "logarithmic" : "linear",
    title: {
      display: true,
      text: titleText,
      color: base.text,
      font: { family: "'Satoshi', sans-serif", size: 11, weight: "700" },
    },
    grid: {
      drawTicks: false,
      // Suppress the minor log-scale gridlines so the plot does not turn into a
      // barcode; only decades and 3x midpoints get a rule.
      color: m.log
        ? (ctx) => {
            const v = ctx.tick && ctx.tick.value;
            if (!v || v <= 0) return "transparent";
            const mant = v / Math.pow(10, Math.floor(Math.log10(v)));
            return Math.abs(mant - 1) < 0.01 || Math.abs(mant - 3) < 0.01
              ? base.grid
              : "transparent";
          }
        : base.grid,
    },
    border: { display: false },
    ticks: {
      color: base.text,
      font: { family: "'JetBrains Mono', monospace", size: 10 },
      maxRotation: 0,
      autoSkip: !m.log,
      maxTicksLimit: 9,
      callback(value) {
        // A logarithmic scale emits every 1-2-3...9 step per decade, which is far
        // too dense to label. Keep decades and their 3x midpoints only.
        if (m.log) {
          const exp = Math.log10(value);
          const mant = value / Math.pow(10, Math.floor(exp));
          if (Math.abs(mant - 1) > 0.01 && Math.abs(mant - 3) > 0.01) return "";
        }
        return m.axis(value);
      },
    },
  };
}

function destroy(key) {
  if (charts[key]) {
    charts[key].destroy();
    delete charts[key];
  }
}

/* ── Scatter ───────────────────────────────────────────────────────────── */
function renderScatter() {
  destroy("scatter");
  const base = chartBase();
  const { x, y } = state.axes;
  const mx = METRICS[x];
  const my = METRICS[y];

  const rows = state.view.filter((d) => d[x] != null && d[y] != null);
  // Size reference is the 90th percentile of FTE, not the max: a single 110k-FTE
  // institution would otherwise flatten every other dot to the minimum radius.
  const ftes = rows.map((d) => d.fte || 0).sort((a, b) => a - b);
  const fteRef = Math.max(1, ftes[Math.floor(0.9 * (ftes.length - 1))] || 1);
  // Dot radii are tuned for a wide canvas; on a phone the same radii merge into
  // one solid blob, so scale them down with the plot width.
  const canvasW = document.getElementById("scatter").clientWidth || 1000;
  const rScale = Math.max(0.45, Math.min(1, canvasW / 900));

  document.getElementById("scatter-sub").textContent =
    my.label +
    " vs " +
    mx.label +
    " · " +
    rows.length.toLocaleString("en-US") +
    " reporting";

  const legend = document.getElementById("scatter-legend");
  legend.textContent = "";
  CONTROLS.forEach(({ key, varName }) => {
    const n = rows.filter((d) => d.control === key).length;
    const item = document.createElement("span");
    item.className = "legend__item";
    item.innerHTML =
      '<span class="legend__swatch" style="--sw:' +
      css(varName) +
      '"></span>' +
      key +
      ' <span class="mono">' +
      n.toLocaleString("en-US") +
      "</span>";
    legend.append(item);
  });

  const datasets = CONTROLS.map(({ key, varName }) => {
    const color = css(varName);
    return {
      label: key,
      data: rows
        .filter((d) => d.control === key)
        .map((d) => ({
          x: d[x],
          y: d[y],
          r:
            rScale *
            (2 + 6.5 * Math.sqrt(Math.min(d.fte || 0, fteRef) / fteRef)),
          ref: d,
        })),
      // Dense overplotting on a dark surface blooms additively, so the dark theme
      // gets a lower fill alpha and no per-dot stroke.
      backgroundColor: color + (isDark() ? "38" : "73"),
      borderColor: color,
      borderWidth: isDark() ? 0 : 0.5,
      hoverBorderWidth: 2,
      hoverBackgroundColor: color,
    };
  });

  charts.scatter = new Chart(document.getElementById("scatter"), {
    type: "bubble",
    data: { datasets },
    options: {
      responsive: base.responsive,
      maintainAspectRatio: base.maintainAspectRatio,
      animation: false,
      scales: {
        x: axisConf(base, x, mx.label),
        y: axisConf(base, y, my.label),
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...base.tooltip,
          callbacks: {
            title: (items) => items[0].raw.ref.name,
            label(item) {
              const d = item.raw.ref;
              return [
                d.city + ", " + d.state + " · " + d.control,
                my.short + ": " + my.fmt(d[y]),
                mx.short + ": " + mx.fmt(d[x]),
                "FTE: " + fmt.int(d.fte),
              ];
            },
          },
        },
      },
      onClick(evt, elements) {
        if (elements.length) openDrawer(elements[0].element.$context.raw.ref);
      },
    },
  });
}

/* ── Enrollment trend + forecast ───────────────────────────────────────── */
const FORECAST_YEARS = 3;

function renderTrend() {
  destroy("trend");
  const base = chartBase();
  const years = state.meta.trendYears;

  // Restrict the aggregate to institutions reporting every year so movement
  // reflects real enrollment change, not panel composition change.
  const panel = state.view.filter((d) => d.complete);
  const totals = years.map((_, i) =>
    panel.reduce((s, d) => s + d.series[i], 0),
  );

  document.getElementById("trend-sub").textContent =
    "Aggregate undergraduate FTE · " +
    panel.length.toLocaleString("en-US") +
    " institutions with a complete " +
    years[0] +
    "–" +
    years[years.length - 1] +
    " series";

  const foot = document.getElementById("trend-foot");

  if (panel.length < 3) {
    foot.textContent =
      "Not enough institutions with a complete series to fit a trend. Widen the filters.";
    charts.trend = new Chart(document.getElementById("trend"), {
      type: "line",
      data: { labels: years, datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: base.text } },
          y: { ticks: { color: base.text } },
        },
        plugins: { legend: { display: false } },
      },
    });
    return;
  }

  const xs = years.map((_, i) => i);
  const { slope, intercept } = ols(xs, totals);
  const futureYears = [];
  for (let k = 1; k <= FORECAST_YEARS; k++)
    futureYears.push(years[years.length - 1] + k);
  const labels = [...years, ...futureYears];

  const fitted = labels.map((_, i) => intercept + slope * i);
  const actual = [...totals, ...futureYears.map(() => null)];
  // Join the dashed segment to the last actual point so the line is continuous.
  const forecast = labels.map((_, i) =>
    i < years.length - 1 ? null : intercept + slope * i,
  );
  forecast[years.length - 1] = totals[totals.length - 1];

  const primary = css("--color-primary");
  const accent = css("--color-accent");

  const pctChange = totals[0]
    ? (totals[totals.length - 1] - totals[0]) / totals[0]
    : 0;
  const projected = intercept + slope * (labels.length - 1);
  foot.textContent =
    "Observed change " +
    fmt.signedPct(pctChange) +
    " over " +
    (years.length - 1) +
    " years. OLS trend implies " +
    fmt.compact(projected) +
    " FTE by " +
    futureYears[futureYears.length - 1] +
    " (" +
    fmt.signedPct(slope / (totals[totals.length - 1] || 1)) +
    " per year). Descriptive trend only.";

  charts.trend = new Chart(document.getElementById("trend"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Reported FTE",
          data: actual,
          borderColor: primary,
          backgroundColor: primary + "22",
          borderWidth: 2,
          pointRadius: 2.5,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.25,
        },
        {
          label: "OLS trend",
          data: forecast,
          borderColor: accent,
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: false,
        },
        {
          label: "Fitted",
          data: fitted.slice(0, years.length),
          borderColor: accent + "55",
          borderWidth: 1,
          borderDash: [2, 3],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 700, easing: "easeOutQuart" },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            maxRotation: 0,
            autoSkipPadding: 12,
          },
        },
        y: {
          grid: { color: base.grid, drawTicks: false },
          border: { display: false },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            callback: (v) => fmt.compact(v),
          },
        },
      },
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: {
            color: base.text,
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: true,
            pointStyle: "line",
            font: { family: "'Satoshi', sans-serif", size: 11 },
            filter: (item) => item.text !== "Fitted",
          },
        },
        tooltip: {
          ...base.tooltip,
          displayColors: true,
          callbacks: {
            label: (item) =>
              item.dataset.label +
              ": " +
              (item.raw == null ? "—" : fmt.int(item.raw)),
          },
        },
      },
    },
  });
}

/* ── Distribution histogram ────────────────────────────────────────────── */
function renderDist() {
  destroy("dist");
  const base = chartBase();
  const key = state.distMetric;
  const m = METRICS[key];

  const rows = state.view.filter((d) => d[key] != null);
  document.getElementById("dist-sub").textContent =
    m.label + " · " + rows.length.toLocaleString("en-US") + " reporting";

  const foot = document.getElementById("dist-foot");

  if (rows.length < 5) {
    foot.textContent = "Too few reporting institutions to bin.";
    charts.dist = new Chart(document.getElementById("dist"), {
      type: "bar",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
    return;
  }

  const values = rows.map((d) => d[key]);
  // Trim the top 1% so a handful of extreme values don't flatten the shape.
  const sorted = [...values].sort((a, b) => a - b);
  const lo = sorted[0];
  const hi =
    sorted[Math.floor(sorted.length * 0.99)] || sorted[sorted.length - 1];
  const span = hi - lo || 1;
  const bins = 18;
  const width = span / bins;

  const labels = [];
  for (let i = 0; i < bins; i++) {
    labels.push(m.axis(lo + i * width));
  }

  const datasets = CONTROLS.map(({ key: control, varName }) => {
    const counts = new Array(bins).fill(0);
    rows.forEach((d) => {
      if (d.control !== control) return;
      let idx = Math.floor((d[key] - lo) / width);
      if (idx < 0) idx = 0;
      if (idx >= bins) idx = bins - 1;
      counts[idx] += 1;
    });
    return {
      label: control,
      data: counts,
      backgroundColor: css(varName),
      borderWidth: 0,
      borderRadius: 2,
    };
  });

  const med = median(values);
  foot.textContent =
    "Median " +
    m.fmt(med) +
    " · range " +
    m.fmt(lo) +
    " to " +
    m.fmt(hi) +
    " (top 1% trimmed).";

  charts.dist = new Chart(document.getElementById("dist"), {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 600, easing: "easeOutQuart" },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          border: { display: false },
          title: {
            display: true,
            text: m.label,
            color: base.text,
            font: { family: "'Satoshi', sans-serif", size: 11, weight: "700" },
          },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 9 },
            maxRotation: 0,
            autoSkip: true,
            autoSkipPadding: 8,
          },
        },
        y: {
          stacked: true,
          grid: { color: base.grid, drawTicks: false },
          border: { display: false },
          title: {
            display: true,
            text: "Institutions",
            color: base.text,
            font: { family: "'Satoshi', sans-serif", size: 11, weight: "700" },
          },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 10 },
          },
        },
      },
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: {
            color: base.text,
            boxWidth: 10,
            boxHeight: 10,
            font: { family: "'Satoshi', sans-serif", size: 11 },
          },
        },
        tooltip: {
          ...base.tooltip,
          displayColors: true,
          mode: "index",
          intersect: false,
        },
      },
    },
  });
}

/* ── Map ───────────────────────────────────────────────────────────────── */
function renderMap() {
  const svg = document.getElementById("map");
  const geo = state.map;
  const key = state.mapMetric;
  const m = METRICS[key];

  svg.setAttribute("viewBox", geo.viewBox);
  svg.textContent = "";

  const project = d3
    .geoAlbersUsa()
    .scale(geo.projection.scale)
    .translate(geo.projection.translate);

  const statesGroup = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "g",
  );
  geo.states.forEach((s) => {
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", s.d);
    p.setAttribute("class", "map__state");
    statesGroup.append(p);
  });
  svg.append(statesGroup);

  const rows = state.view.filter((d) => d.lat != null && d.lon != null);
  const withMetric = rows.filter((d) => d[key] != null).map((d) => d[key]);
  const sorted = [...withMetric].sort((a, b) => a - b);
  const ramp = RAMP();
  // Quantile breaks so each shade carries a similar share of institutions.
  const breaks = [0.2, 0.4, 0.6, 0.8].map(
    (q) => sorted[Math.floor(q * (sorted.length - 1))],
  );
  const shade = (v) => {
    if (v == null) return css("--color-text-faint");
    let i = 0;
    while (i < breaks.length && v >= breaks[i]) i++;
    return ramp[i + 1];
  };

  const maxFte = Math.max(1, ...rows.map((d) => d.fte || 0));
  const dots = document.createElementNS("http://www.w3.org/2000/svg", "g");
  let plotted = 0;

  rows.forEach((d) => {
    const xy = project([d.lon, d.lat]);
    if (!xy) return; // outside the albersUsa composite (e.g. territories)
    plotted++;
    const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    c.setAttribute("cx", xy[0].toFixed(1));
    c.setAttribute("cy", xy[1].toFixed(1));
    c.setAttribute(
      "r",
      (1.6 + 6 * Math.sqrt((d.fte || 0) / maxFte)).toFixed(2),
    );
    c.setAttribute("fill", shade(d[key]));
    c.setAttribute("fill-opacity", "0.85");
    c.setAttribute("class", "map__dot");
    c.addEventListener("mouseenter", () => showTip(d, xy, key));
    c.addEventListener("mouseleave", hideTip);
    c.addEventListener("click", () => openDrawer(d));
    dots.append(c);
  });
  svg.append(dots);

  document.getElementById("map-sub").textContent =
    plotted.toLocaleString("en-US") +
    " institutions plotted · dots shaded by " +
    m.label.toLowerCase() +
    ", sized by FTE";

  const legend = document.getElementById("map-legend");
  legend.textContent = "";
  if (sorted.length) {
    const low = document.createElement("span");
    low.className = "mono";
    low.textContent = m.fmt(sorted[0]);
    const rampEl = document.createElement("span");
    rampEl.className = "legend__ramp";
    ramp.slice(1).forEach((c) => {
      const s = document.createElement("span");
      s.style.background = c;
      rampEl.append(s);
    });
    const high = document.createElement("span");
    high.className = "mono";
    high.textContent = m.fmt(sorted[sorted.length - 1]);
    const note = document.createElement("span");
    note.className = "muted";
    note.textContent = "quintiles · grey = not reported";
    legend.append(low, rampEl, high, note);
  }
}

function showTip(d, xy, key) {
  const tip = document.getElementById("maptip");
  const box = document.getElementById("mapbox");
  const svg = document.getElementById("map");
  const vb = svg.viewBox.baseVal;
  const rect = svg.getBoundingClientRect();
  const boxRect = box.getBoundingClientRect();
  const scale = rect.width / vb.width;
  tip.hidden = false;
  tip.innerHTML =
    "<strong>" +
    d.name +
    "</strong><span>" +
    d.city +
    ", " +
    d.state +
    " · " +
    METRICS[key].short +
    " " +
    (METRICS[key].fmt(d[key]) || "n/r") +
    "</span>";
  tip.style.left = (xy[0] - vb.x) * scale + (rect.left - boxRect.left) + "px";
  tip.style.top = (xy[1] - vb.y) * scale + (rect.top - boxRect.top) + "px";
}

function hideTip() {
  document.getElementById("maptip").hidden = true;
}

/* ── Table ─────────────────────────────────────────────────────────────── */
const COLUMNS = [
  { key: "name", label: "Institution", type: "name" },
  { key: "control", label: "Control", type: "text" },
  { key: "fte", label: "FTE" },
  { key: "sfr", label: "S:F" },
  { key: "gradRate", label: "Grad 150%" },
  { key: "retention", label: "Retention" },
  { key: "admitRate", label: "Admit" },
  { key: "pellPct", label: "Pell" },
  { key: "tuitionIn", label: "Tuition (in)" },
  { key: "cagr", label: "Growth" },
  { key: "series", label: "Trend", type: "spark", sortable: false },
];

function renderTable() {
  const thead = document.getElementById("thead");
  const tbody = document.getElementById("tbody");
  const { sort } = state;

  const rows = [...state.view].sort((a, b) => {
    const k = sort.key;
    const av = a[k];
    const bv = b[k];
    if (av == null && bv == null) return 0;
    if (av == null) return 1; // nulls always last
    if (bv == null) return -1;
    if (typeof av === "string") return sort.dir * av.localeCompare(bv);
    return sort.dir * (av - bv);
  });

  thead.textContent = "";
  const tr = document.createElement("tr");
  COLUMNS.forEach((col) => {
    const th = document.createElement("th");
    th.scope = "col";
    const active = sort.key === col.key;
    th.textContent = col.label + (active ? (sort.dir === 1 ? " ↑" : " ↓") : "");
    if (col.sortable === false) {
      th.style.cursor = "default";
      th.setAttribute("aria-sort", "none");
    } else {
      th.setAttribute(
        "aria-sort",
        active ? (sort.dir === 1 ? "ascending" : "descending") : "none",
      );
      th.addEventListener("click", () => {
        if (sort.key === col.key) sort.dir *= -1;
        else {
          sort.key = col.key;
          sort.dir = col.type === "name" || col.type === "text" ? 1 : -1;
        }
        renderTable();
      });
    }
    tr.append(th);
  });
  thead.append(tr);

  const shown = rows.slice(0, state.limit);
  tbody.textContent = "";

  if (!rows.length) {
    const empty = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = COLUMNS.length;
    td.style.textAlign = "center";
    td.style.padding = "2rem";
    td.style.fontFamily = "var(--font-body)";
    td.className = "muted";
    td.textContent = "No institutions match these filters. Try resetting.";
    empty.append(td);
    tbody.append(empty);
  }

  shown.forEach((d) => {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    if (state.selected && state.selected.id === d.id)
      row.setAttribute("aria-selected", "true");
    COLUMNS.forEach((col) => {
      const td = document.createElement("td");
      if (col.type === "name") {
        td.className = "cell-name";
        td.innerHTML =
          "<strong>" +
          escapeHtml(d.name) +
          "</strong><small>" +
          escapeHtml((d.city || "") + ", " + (d.state || "")) +
          "</small>";
        td.title = d.name;
      } else if (col.type === "text") {
        td.style.fontFamily = "var(--font-body)";
        td.style.color = controlColor(d.control);
        td.textContent = (d.control || "").replace("Private ", "");
      } else if (col.type === "spark") {
        td.innerHTML = sparkline(d.series);
      } else {
        td.innerHTML = or(METRICS[col.key].fmt(d[col.key]));
      }
      row.append(td);
    });
    row.addEventListener("click", () => openDrawer(d));
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter") openDrawer(d);
    });
    tbody.append(row);
  });

  document.getElementById("table-showing").textContent =
    "Showing " +
    shown.length.toLocaleString("en-US") +
    " of " +
    rows.length.toLocaleString("en-US");
  document.getElementById("more").hidden = shown.length >= rows.length;
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(
    /[&<>"]/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
      })[c],
  );
}

function sparkline(series) {
  const pts = series.map((v, i) => [i, v]).filter(([, v]) => v != null);
  if (pts.length < 2) return NA;
  const vals = pts.map(([, v]) => v);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const w = 66;
  const h = 18;
  const n = series.length - 1;
  const d = pts
    .map(([i, v], k) => {
      const x = (i / n) * w + 1;
      const y = h - ((v - lo) / span) * (h - 2) - 1;
      return (k ? "L" : "M") + x.toFixed(1) + "," + y.toFixed(1);
    })
    .join("");
  return (
    '<svg class="spark" viewBox="0 0 ' +
    (w + 2) +
    " " +
    h +
    '"><path d="' +
    d +
    '"/></svg>'
  );
}

/* ── Peer groups ───────────────────────────────────────────────────────── */
const PEER_FEATURES = ["fte", "sfr", "pellPct", "tuitionIn"];

/**
 * Nearest-neighbour peer group in standardized feature space, mirroring
 * src/features/peer_groups.py: restrict to comparable institutions, then rank
 * by distance over z-scored size, staffing, aid intensity and price.
 */
function peerGroup(target, k = 8) {
  const usable = (d) => PEER_FEATURES.every((f) => d[f] != null);
  if (!usable(target)) return { peers: [], scope: null };

  const tiers = [
    {
      test: (d) => d.control === target.control && d.family === target.family,
      label: "same control and Carnegie family",
    },
    {
      test: (d) => d.control === target.control && d.level === target.level,
      label: "same control and level",
    },
    { test: (d) => d.control === target.control, label: "same control" },
  ];

  let pool = [];
  let scope = null;
  for (const tier of tiers) {
    pool = state.all.filter(
      (d) => d.id !== target.id && usable(d) && tier.test(d),
    );
    if (pool.length >= k) {
      scope = tier.label;
      break;
    }
  }
  if (!pool.length) return { peers: [], scope: null };

  const value = (d, f) => (f === "fte" ? Math.log10(Math.max(1, d.fte)) : d[f]);
  const stats = {};
  PEER_FEATURES.forEach((f) => {
    const col = pool.map((d) => value(d, f));
    stats[f] = { mu: mean(col), sd: stdev(col) || 1 };
  });

  const dist = (d) =>
    Math.sqrt(
      PEER_FEATURES.reduce((s, f) => {
        const z = (value(d, f) - stats[f].mu) / stats[f].sd;
        const zt = (value(target, f) - stats[f].mu) / stats[f].sd;
        return s + (z - zt) ** 2;
      }, 0),
    );

  const peers = pool
    .map((d) => ({ d, dist: dist(d) }))
    .sort((a, b) => a.dist - b.dist)
    .slice(0, k)
    .map((p) => p.d);

  return { peers, scope, poolSize: pool.length };
}

/* ── Drawer ────────────────────────────────────────────────────────────── */
const DRAWER_METRICS = [
  "fte",
  "sfr",
  "gradRate",
  "retention",
  "admitRate",
  "yieldRate",
  "pellPct",
  "tuitionIn",
  "tuitionOut",
  "cagr",
];
const BENCH_METRICS = ["gradRate", "retention", "sfr", "pellPct", "tuitionIn"];

function openDrawer(d, keepScroll) {
  state.selected = d;
  const drawer = document.getElementById("drawer");
  const scrim = document.getElementById("scrim");
  const inner = document.getElementById("drawer-inner");
  const prevScroll = keepScroll ? inner.scrollTop : 0;

  destroy("detail");
  drawer.hidden = false;
  scrim.hidden = false;
  if (keepScroll) {
    drawer.style.animation = "none";
    scrim.style.animation = "none";
  } else {
    drawer.style.animation = "";
    scrim.style.animation = "";
  }

  const { peers, scope, poolSize } = peerGroup(d);
  const years = state.meta.trendYears;

  inner.textContent = "";
  inner.innerHTML =
    '<div class="dtl__top"><div><h2 class="dtl__name">' +
    escapeHtml(d.name) +
    '</h2><p class="dtl__where">' +
    escapeHtml((d.city || "") + ", " + (d.state || "")) +
    ' · UNITID <span class="mono">' +
    d.id +
    "</span></p></div>" +
    '<button class="btn btn--icon" id="drawer-close" aria-label="Close detail">' +
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>' +
    '<div class="dtl__tags">' +
    tag(d.control, controlColor(d.control)) +
    tag(d.level) +
    (d.family ? tag(d.family) : "") +
    (d.hbcu ? tag("HBCU", css("--color-accent")) : "") +
    "</div>" +
    (d.carnegie
      ? '<p class="dtl__carnegie">' + escapeHtml(d.carnegie) + "</p>"
      : "") +
    '<section class="dtl__section"><h3 class="dtl__h">Reported metrics · ' +
    state.meta.primaryYear +
    '</h3><dl class="dtl__grid">' +
    DRAWER_METRICS.map(
      (k) =>
        '<div class="dtl__metric"><dt>' +
        METRICS[k].label +
        "</dt><dd>" +
        or(METRICS[k].fmt(d[k])) +
        "</dd></div>",
    ).join("") +
    "</dl></section>" +
    '<section class="dtl__section"><h3 class="dtl__h">Undergraduate FTE, ' +
    years[0] +
    "–" +
    years[years.length - 1] +
    '</h3><div class="dtl__chart"><canvas id="detail-chart"></canvas></div></section>' +
    (peers.length
      ? '<section class="dtl__section"><h3 class="dtl__h">Benchmark vs peer median</h3>' +
        benchmarkHtml(d, peers) +
        '<div class="bench__legend"><span>▌ this institution</span><span style="color:var(--color-accent)">▏ peer median</span></div>' +
        "</section>" +
        '<section class="dtl__section"><h3 class="dtl__h">Nearest peers · ' +
        peers.length +
        " of " +
        poolSize.toLocaleString("en-US") +
        '</h3><p class="card__foot">Matched on ' +
        scope +
        ', ranked by distance over standardized FTE, student-to-faculty ratio, Pell share and tuition.</p><div class="peer">' +
        peers
          .map(
            (p) =>
              '<div class="peer__row"><span class="peer__name" title="' +
              escapeHtml(p.name) +
              '">' +
              escapeHtml(p.name) +
              '</span><span class="peer__val">' +
              (fmt.pct(p.gradRate) || "—") +
              "</span></div>",
          )
          .join("") +
        '</div><p class="card__foot">Value shown is the 150% graduation rate.</p></section>'
      : '<section class="dtl__section"><h3 class="dtl__h">Peer group</h3><p class="card__foot">' +
        "This institution does not report all four peer-matching metrics (FTE, student-to-faculty ratio, Pell share, tuition), so no peer group can be formed.</p></section>");

  document
    .getElementById("drawer-close")
    .addEventListener("click", closeDrawer);
  if (keepScroll) inner.scrollTop = prevScroll;

  renderDetailChart(d, peers);
  renderTableSelection();
}

function tag(text, color) {
  if (!text) return "";
  return (
    '<span class="tag">' +
    (color
      ? '<span class="chip__dot" style="--dot:' + color + '"></span>'
      : "") +
    escapeHtml(text) +
    "</span>"
  );
}

function benchmarkHtml(d, peers) {
  return (
    '<div class="bench">' +
    BENCH_METRICS.map((k) => {
      const m = METRICS[k];
      const self = d[k];
      const peerMed = median(peers.map((p) => p[k]));
      if (self == null || peerMed == null) return "";
      const max = Math.max(self, peerMed) * 1.15 || 1;
      const selfPct = Math.min(100, (self / max) * 100);
      const peerPct = Math.min(100, (peerMed / max) * 100);
      const diff = peerMed ? (self - peerMed) / peerMed : 0;
      return (
        '<div class="bench__row"><div class="bench__head"><span>' +
        m.label +
        "</span><span><b>" +
        m.fmt(self) +
        "</b> vs " +
        m.fmt(peerMed) +
        ' <span class="mono">(' +
        fmt.signedPct(diff) +
        ")</span></span></div>" +
        '<div class="bench__track"><span class="bench__fill" style="width:' +
        selfPct.toFixed(1) +
        '%"></span><span class="bench__peer" style="left:' +
        peerPct.toFixed(1) +
        '%"></span></div></div>'
      );
    }).join("") +
    "</div>"
  );
}

function renderDetailChart(d, peers) {
  const base = chartBase();
  const years = state.meta.trendYears;
  const primary = css("--color-primary");
  const accent = css("--color-accent");

  const peerMedian = years.map((_, i) => median(peers.map((p) => p.series[i])));

  charts.detail = new Chart(document.getElementById("detail-chart"), {
    type: "line",
    data: {
      labels: years,
      datasets: [
        {
          label: d.name,
          data: d.series,
          borderColor: primary,
          backgroundColor: primary + "22",
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.25,
          spanGaps: true,
        },
        {
          label: "Peer median",
          data: peers.length ? peerMedian : [],
          borderColor: accent,
          borderWidth: 1.5,
          borderDash: [4, 3],
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: false,
          spanGaps: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 9 },
            maxRotation: 0,
            autoSkipPadding: 10,
          },
        },
        y: {
          grid: { color: base.grid, drawTicks: false },
          border: { display: false },
          ticks: {
            color: base.text,
            font: { family: "'JetBrains Mono', monospace", size: 9 },
            callback: (v) => fmt.compact(v),
          },
        },
      },
      plugins: {
        legend: {
          display: peers.length > 0,
          position: "bottom",
          labels: {
            color: base.text,
            boxWidth: 8,
            boxHeight: 8,
            usePointStyle: true,
            pointStyle: "line",
            font: { family: "'Satoshi', sans-serif", size: 10 },
            generateLabels: (chart) =>
              chart.data.datasets.map((ds, i) => ({
                text: i === 0 ? "This institution" : "Peer median",
                strokeStyle: ds.borderColor,
                fillStyle: ds.borderColor,
                lineWidth: 2,
                lineDash: ds.borderDash || [],
                datasetIndex: i,
                hidden: false,
              })),
          },
        },
        tooltip: {
          ...base.tooltip,
          displayColors: true,
          callbacks: {
            label: (item) =>
              (item.datasetIndex === 0 ? "FTE" : "Peer median") +
              ": " +
              (item.raw == null ? "—" : fmt.int(item.raw)),
          },
        },
      },
    },
  });
}

function renderTableSelection() {
  document
    .querySelectorAll("#tbody tr")
    .forEach((tr) => tr.removeAttribute("aria-selected"));
  const rows = [...document.querySelectorAll("#tbody tr")];
  const names = [...document.querySelectorAll("#tbody .cell-name")];
  const idx = names.findIndex(
    (n) => n.title === (state.selected && state.selected.name),
  );
  if (idx >= 0) rows[idx].setAttribute("aria-selected", "true");
}

function closeDrawer() {
  state.selected = null;
  document.getElementById("drawer").hidden = true;
  document.getElementById("scrim").hidden = true;
  destroy("detail");
  document
    .querySelectorAll("#tbody tr")
    .forEach((tr) => tr.removeAttribute("aria-selected"));
}

/* ── CSV export ────────────────────────────────────────────────────────── */
function exportCsv() {
  const keys = [
    "id",
    "name",
    "city",
    "state",
    "control",
    "level",
    "family",
    "carnegie",
    "fte",
    "sfr",
    "gradRate",
    "retention",
    "admitRate",
    "yieldRate",
    "pellPct",
    "pellAvg",
    "tuitionIn",
    "tuitionOut",
    "cagr",
  ];
  const years = state.meta.trendYears.map((y) => "fte_" + y);
  const head = [...keys, ...years].join(",");
  const cell = (v) => {
    if (v == null) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const body = state.view
    .map((d) =>
      [...keys.map((k) => cell(d[k])), ...d.series.map((v) => cell(v))].join(
        ",",
      ),
    )
    .join("\n");

  const blob = new Blob([head + "\n" + body], {
    type: "text/csv;charset=utf-8",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "ipeds-" + state.meta.primaryYear + "-filtered.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* ── Go ────────────────────────────────────────────────────────────────── */
boot().catch((err) => {
  console.error(err);
  document.getElementById("loading").innerHTML =
    '<p class="loading__text">Could not load the IPEDS panel. Rebuild it with ' +
    '<span class="mono">python -m src.ingest.build_dashboard_data</span>.</p>';
});
