// app.js - entry point. Handles the top navigation, the analyst sub-tabs, the theme toggle
// and error messages, and starts each page module the first time it is opened.
import * as fit from "./pages/fit.js";
import * as explore from "./pages/explore.js";
import * as compare from "./pages/compare.js";
import * as insights from "./pages/insights.js";
import * as stats from "./pages/stats.js";
import * as models from "./pages/models.js";
import * as tryit from "./pages/tryit.js";
import * as atlas from "./pages/atlas.js";
import { initData } from "./pages/info.js";

const ctx = {
  go: (tab) => showTab(tab),
  async openRole(role) { await showTab("explore"); await explore.show(role); },
  async openCompare(a, b) { await showTab("compare"); await compare.show(a, b); },
};

const pages = {
  fit: { init: () => fit.init(ctx), redraw: fit.redraw },
  explore: { init: () => explore.init(ctx), redraw: explore.redraw },
  compare: { init: compare.init, redraw: compare.redraw },
  insights: { init: insights.init, redraw: insights.redraw },
  research: { init: () => showSub("stats") },
};
const subs = {
  stats: { init: stats.init, redraw: stats.redraw },
  models: { init: models.init, redraw: models.redraw },
  playground: { init: tryit.init, redraw: tryit.redraw },
  distances: { init: () => atlas.init(ctx), redraw: atlas.redraw },
  data: { init: initData },
};
const started = {}, subStarted = {};

function showError(err) {
  const box = document.getElementById("status");
  box.textContent = err.message || String(err);
  box.hidden = false;
  console.error(err);
}

function resizeCharts(scope) {
  document.querySelectorAll(`${scope} .js-plotly-plot`).forEach((el) => Plotly.Plots.resize(el));
}

async function showTab(name) {
  if (!pages[name]) name = "fit";
  document.querySelectorAll(".nav-link").forEach((t) => {
    if (t.dataset.tab === name) t.setAttribute("aria-current", "page"); else t.removeAttribute("aria-current");
  });
  document.querySelectorAll(".page").forEach((p) => { p.hidden = p.id !== `page-${name}`; });
  history.replaceState(null, "", `#${name}`);
  window.scrollTo({ top: 0 });
  try {
    if (!started[name]) started[name] = pages[name].init();
    await started[name];
    resizeCharts(`#page-${name}`);
  } catch (err) {
    started[name] = null;
    showError(err);
  }
}

async function showSub(name) {
  document.querySelectorAll("#research-tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.sub === name));
  document.querySelectorAll(".sub").forEach((s) => { s.hidden = s.id !== `sub-${name}`; });
  try {
    if (!subStarted[name]) subStarted[name] = subs[name].init();
    await subStarted[name];
    resizeCharts(`#sub-${name}`);
  } catch (err) {
    subStarted[name] = null;
    showError(err);
  }
}

function redrawAll() {
  Object.entries(pages).forEach(([k, p]) => { if (started[k] && p.redraw) p.redraw(); });
  Object.entries(subs).forEach(([k, p]) => { if (subStarted[k] && p.redraw) p.redraw(); });
}

// ---------------------------------------------------------------- theme toggle
const root = document.documentElement;
const toggle = document.getElementById("theme-toggle");
const isDark = () => (root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches);
const syncToggle = () => { toggle.textContent = isDark() ? "Light" : "Dark"; };
try { const saved = localStorage.getItem("theme"); if (saved) root.dataset.theme = saved; } catch { /* storage blocked */ }
syncToggle();
toggle.addEventListener("click", () => {
  root.dataset.theme = isDark() ? "light" : "dark";
  try { localStorage.setItem("theme", root.dataset.theme); } catch { /* ignore */ }
  syncToggle();
  redrawAll();
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (root.dataset.theme) return;
  syncToggle();
  redrawAll();
});

// ------------------------------------------------------------------- navigation
document.querySelectorAll(".nav-link").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
document.querySelector(".brand").addEventListener("click", (e) => { e.preventDefault(); showTab("fit"); });
document.getElementById("research-tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-sub]");
  if (b) showSub(b.dataset.sub);
});
showTab(location.hash.slice(1) || "fit");
