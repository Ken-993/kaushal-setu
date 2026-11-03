// explore.js - role cards, one role's details, and the "similar roles" orbit chart.
import { api } from "../api.js";
import { cityName, esc, fmtBand, isRealSkill, plot, shortBand, tokens } from "../charts.js";

const VIEWS = { skills: "Skills", competency: "Skill areas", salary: "Pay", career: "Seniority", blended: "Overall" };
const VIEW_HELP = {
  skills: "alike in the specific skills employers list",
  competency: "alike in the mix of skill areas (coding, maths, AI, big data, dashboards)",
  salary: "alike in how much they pay",
  career: "alike in experience asked for and pay level",
  blended: "alike across skills, skill areas, pay and seniority together",
};
const SHOW = 10;          // roles drawn in the orbit (the list shows all)
const C = 340, RMIN = 100, RMAX = 300;

let ctx, list = [], view = "skills", current = "Data Scientist", sim = null, opts = null;
const $ = (id) => document.getElementById(id);

export async function init(appCtx) {
  ctx = appCtx;
  [list, opts] = await Promise.all([api.profiles(), api.options()]);
  $("orbit-view").innerHTML = Object.entries(VIEWS).map(([k, v]) =>
    `<button type="button" role="radio" data-view="${k}" aria-checked="${k === view}">${v}</button>`).join("");
  $("orbit-view").addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-view]");
    if (!b) return;
    view = b.dataset.view;
    $("orbit-view").querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", x === b));
    await loadView();
    drawOrbit();
  });
  renderGrid();
  $("role-grid").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-role]");
    if (b) select(b.dataset.role, true);
  });
  $("near-list").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-role]");
    if (b) select(b.dataset.role);
  });
  $("orbit").addEventListener("click", (e) => {
    const g = e.target.closest("[data-role]");
    if (g) select(g.dataset.role);
  });
  $("orbit").addEventListener("keydown", (e) => {
    const g = e.target.closest("[data-role]");
    if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(g.dataset.role); }
  });
  $("role-body").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    if (b.dataset.act === "fit") ctx.go("fit");
    if (b.dataset.act === "compare") ctx.openCompare(current, b.dataset.other);
  });
  await loadView();
  await select(current);
}

export async function show(role) {
  if (role) await select(role, true);
}

async function loadView() {
  sim = await api.similarity(view);
}

function renderGrid() {
  const tile = (r) => `
    <button type="button" class="role-tile" data-role="${esc(r.role)}" aria-pressed="${r.role === current}">
      <strong>${esc(r.role)}</strong>
      <span class="tile-pay">${fmtBand(r.band_median)}</span>
      <small>about ${Math.round(r.exp_min_mean)} yrs experience, ${r.n.toLocaleString()} postings</small>
    </button>`;
  $("role-grid").innerHTML =
    `<h2>Data roles</h2>${list.filter((r) => r.group === "data").map(tile).join("")}` +
    `<h2>Related roles</h2>${list.filter((r) => r.group !== "data").map(tile).join("")}`;
}

async function select(role, scroll = false) {
  current = role;
  $("role-grid").querySelectorAll(".role-tile").forEach((b) => b.setAttribute("aria-pressed", b.dataset.role === role));
  const p = await api.profile(role);
  renderDetail(p);
  drawOrbit();
  if (scroll) $("role-head").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ----------------------------------------------------------------- role detail
function renderDetail(p) {
  const ds = p.dsjobs;
  const nearest = p.nearest.skills[0];
  const bars = (items) => items.map(([label, v]) => `
    <li><span>${esc(label)}</span><span class="bar"><span style="width:${Math.max(2, v * 100).toFixed(0)}%"></span></span><span class="pct">${Math.round(v * 100)}%</span></li>`).join("");
  $("role-head").innerHTML = `
    <div class="detail-head">
      <div>
        <h2>${esc(p.role)}</h2>
        <p>${p.group === "data" ? "Data role" : "Related role"}, based on ${p.n.toLocaleString()} job postings. Example titles: ${p.example_titles.slice(0, 3).map(esc).join("; ")}</p>
      </div>
      <dl class="detail-stats">
        <div><dt>Typical pay</dt><dd>${fmtBand(p.band_median)}</dd></div>
        <div><dt>Usual experience</dt><dd>${p.exp_min_median}+ yrs</dd></div>
        <div><dt>Senior titles</dt><dd>${Math.round(p.senior_share * 100)}%</dd></div>
        <div><dt>Advertised average</dt><dd>${ds ? `₹${ds.avg_salary_lakhs} LPA` : "–"}</dd></div>
      </dl>
    </div>`;
  $("role-body").innerHTML = `
    <div class="two-col">
      <div class="card">
        <h3>What employers ask for</h3>
        <p class="muted">Share of ${esc(p.role)} postings that list each skill.</p>
        <ul class="skill-bars">${bars(p.top_skills.filter((s) => isRealSkill(s.skill)).slice(0, 10).map((s) => [s.skill, s.prevalence]))}</ul>
        <h3 style="margin-top:22px">Skill areas</h3>
        <p class="muted">Share of postings asking for each broad area.</p>
        <ul class="skill-bars">${bars(opts.families.map((f) => [opts.family_labels[f], p.family_prevalence[f]]))}</ul>
      </div>
      <div class="card">
        <h3>Pay range</h3>
        <p class="muted">Share of postings in each pay range (₹ lakhs per year).</p>
        <div id="detail-pay" class="chart chart-short"></div>
        <h3 style="margin-top:18px">Where the jobs are</h3>
        <ul class="chips" style="margin-top:8px">${Object.entries(p.top_cities).map(([c, n]) =>
          `<li class="chip">${esc(cityName(c))} (${n})</li>`).join("")}</ul>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:22px">
          <button type="button" class="btn primary" data-act="fit">Check my fit for this role</button>
          <button type="button" class="btn secondary" data-act="compare" data-other="${esc(nearest.role)}">Compare with ${esc(nearest.role)}</button>
        </div>
      </div>
    </div>`;
  const t = tokens();
  plot("detail-pay", [{
    type: "bar", x: opts.bands.map(shortBand), y: p.band_distribution, marker: { color: t.s1 },
    hovertemplate: "%{x}: %{y:.0%} of postings<extra></extra>",
  }], { yaxis: { tickformat: ".0%", rangemode: "tozero" }, xaxis: { gridcolor: "rgba(0,0,0,0)" }, margin: { t: 6, b: 6, l: 6, r: 6 } });
}

// ----------------------------------------------------------------- orbit chart
function similarities() {
  const i = sim.roles.indexOf(current);
  const flat = sim.matrix.flat();
  const max = Math.max(...flat) || 1;
  return sim.roles.map((r, j) => ({ role: r, group: sim.groups[j], n: sim.n[j], s: 1 - sim.matrix[i][j] / max }))
    .filter((x) => x.role !== current).sort((a, b) => b.s - a.s);
}

function wrapName(name, max = 13) {
  const words = name.split(" "), lines = [];
  let line = "";
  for (const w of words) {
    if ((line + " " + w).trim().length > max && line) { lines.push(line); line = w; } else line = (line + " " + w).trim();
  }
  lines.push(line);
  return lines.slice(0, 3);
}

export function redraw() { if (sim) drawOrbit(); }

function drawOrbit() {
  if (!sim) return;
  const t = tokens();
  const all = similarities();
  const shown = all.slice(0, SHOW);
  $("orbit-role").textContent = current;
  const radius = (s) => RMIN + (1 - Math.max(0, Math.min(1, s))) * (RMAX - RMIN);

  // the top 50 degrees stay empty so the ring labels never collide with a role
  const START = -65, SPAN = 310;
  const rings = [0.75, 0.5, 0.25].map((s) => `
    <circle class="ring-line" cx="${C}" cy="${C}" r="${radius(s)}"/>
    <text class="ring-label" x="${C}" y="${C - radius(s) + 4}" text-anchor="middle">${s * 100}%</text>`).join("") +
    `<text class="ring-label" x="${C}" y="${C - RMAX - 22}" text-anchor="middle">rings show % alike</text>`;

  const nodes = shown.map((x, k) => {
    const a = (START + k * (SPAN / Math.max(1, shown.length - 1))) * Math.PI / 180;
    const r = radius(x.s), px = C + r * Math.cos(a), py = C + r * Math.sin(a);
    const nr = 9 + Math.sqrt(x.n) / 4;
    const cos = Math.cos(a), sin = Math.sin(a);
    let tx, ty, anchor;
    if (cos > 0.35) { tx = nr + 8; ty = 5; anchor = "start"; }
    else if (cos < -0.35) { tx = -nr - 8; ty = 5; anchor = "end"; }
    else { tx = 0; ty = sin > 0 ? nr + 18 : -nr - 9; anchor = "middle"; }
    const color = x.group === "data" ? t.s1 : t.sand;
    const pct = Math.round(x.s * 100);
    return `
      <line class="spoke" x1="${C}" y1="${C}" x2="${px.toFixed(1)}" y2="${py.toFixed(1)}"
        stroke-width="${(1 + x.s * 4).toFixed(1)}" stroke-opacity="${(0.15 + x.s * 0.45).toFixed(2)}"/>
      <g class="node" data-role="${esc(x.role)}" tabindex="0" role="button"
         aria-label="${esc(x.role)}, ${pct}% alike. Press Enter to put it in the centre." transform="translate(${px.toFixed(1)} ${py.toFixed(1)})">
        <title>${esc(x.role)}: ${pct}% alike (${VIEWS[view].toLowerCase()})</title>
        <circle class="dot" r="${nr.toFixed(1)}" fill="${color}"/>
        <text x="${tx}" y="${ty}" text-anchor="${anchor}">${esc(x.role)} <tspan class="p">${pct}%</tspan></text>
      </g>`;
  }).join("");

  const lines = wrapName(current);
  const label = lines.map((l, i) => `<tspan x="${C}" dy="${i === 0 ? -(lines.length - 1) * 10 : 20}">${esc(l)}</tspan>`).join("");
  $("orbit").innerHTML = `
    <circle class="ring-fill" cx="${C}" cy="${C}" r="${RMAX + 14}"/>
    ${rings}
    <g class="orbit-layer" style="transform-origin:${C}px ${C}px">${nodes}</g>
    <circle class="center-dot" cx="${C}" cy="${C}" r="${RMIN - 18}"/>
    <text class="center-text" x="${C}" y="${C + 6}" text-anchor="middle">${label}</text>`;
  // one short "burst out" motion when the centre changes
  const layer = $("orbit").querySelector(".orbit-layer");
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    layer.animate([{ opacity: 0, transform: "scale(0.85)" }, { opacity: 1, transform: "scale(1)" }],
      { duration: 450, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" });
  }

  $("near-list").innerHTML = all.map((x, k) => `
    <li><button type="button" data-role="${esc(x.role)}">
      <span class="rank">${k + 1}</span>
      <span><span class="nm">${esc(x.role)}</span><span class="bar"><span style="width:${Math.max(2, x.s * 100).toFixed(0)}%;background:${x.group === "data" ? t.s1 : t.sand}"></span></span></span>
      <span class="v">${Math.round(x.s * 100)}%</span>
    </button></li>`).join("");
  $("orbit-view").title = VIEW_HELP[view];
  document.querySelector(".orbit-head .muted").textContent =
    `Roles closer to the centre are more ${VIEW_HELP[view]}. Blue dots are data roles, sand dots are related roles. Click any role to move it to the middle.`;
}


