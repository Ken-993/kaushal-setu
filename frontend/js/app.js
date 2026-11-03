// app.js - entry point. Handles tabs, the theme toggle and error messages,
// and starts each page module the first time its tab is opened.
import * as atlas from "./pages/atlas.js";
import * as compare from "./pages/compare.js";
import * as stats from "./pages/stats.js";
import * as models from "./pages/models.js";
import * as tryit from "./pages/tryit.js";
import * as resume from "./pages/resume.js";
import { initData, initFindings } from "./pages/info.js";

const pages = {
  atlas: { init: () => atlas.init(ctx), redraw: atlas.redraw },
  compare: { init: compare.init, redraw: compare.redraw },
  findings: { init: initFindings },
  stats: { init: stats.init, redraw: stats.redraw },
  models: { init: models.init, redraw: models.redraw },
  tryit: { init: tryit.init, redraw: tryit.redraw },
  resume: { init: resume.init, redraw: resume.redraw },
  data: { init: initData },
};
const started = {};
let current = "atlas";

const ctx = {
  async openCompare(a, b) {
    await showTab("compare");
    await compare.show(a, b);
  },
};

function showError(err) {
  const box = document.getElementById("status");
  box.textContent = err.message || String(err);
  box.hidden = false;
  console.error(err);
}

async function showTab(name) {
  current = name;
  document.querySelectorAll(".tab").forEach((t) => {
    if (t.dataset.tab === name) t.setAttribute("aria-current", "page"); else t.removeAttribute("aria-current");
  });
  document.querySelectorAll(".page").forEach((p) => { p.hidden = p.id !== `page-${name}`; });
  history.replaceState(null, "", `#${name}`);
  try {
    if (!started[name]) started[name] = pages[name].init();
    await started[name];
    // charts drawn while hidden have zero width; resize them now that they are visible
    document.querySelectorAll(`#page-${name} .js-plotly-plot`).forEach((el) => Plotly.Plots.resize(el));
  } catch (err) {
    started[name] = null;
    showError(err);
  }
}

// ---------------------------------------------------------------- theme toggle
const root = document.documentElement;
const toggle = document.getElementById("theme-toggle");
function isDark() {
  const forced = root.dataset.theme;
  return forced ? forced === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
function syncToggle() { toggle.textContent = isDark() ? "Light" : "Dark"; }
try { const saved = localStorage.getItem("theme"); if (saved) root.dataset.theme = saved; } catch { /* storage blocked */ }
syncToggle();
toggle.addEventListener("click", () => {
  root.dataset.theme = isDark() ? "light" : "dark";
  try { localStorage.setItem("theme", root.dataset.theme); } catch { /* ignore */ }
  syncToggle();
  Object.entries(pages).forEach(([k, p]) => { if (started[k] && p.redraw) p.redraw(); });
});

matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (root.dataset.theme) return; // the toggle overrides the system setting
  syncToggle();
  Object.entries(pages).forEach(([k, p]) => { if (started[k] && p.redraw) p.redraw(); });
});

// ------------------------------------------------------------------------ tabs
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
const first = location.hash.slice(1);
showTab(pages[first] ? first : "atlas");
