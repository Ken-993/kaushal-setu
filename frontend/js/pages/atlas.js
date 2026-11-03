// atlas.js - the role map, the distance heatmap and the dendrogram.
import { api } from "../api.js";
import { esc, pct, plot, seqScale, tokens } from "../charts.js";

const state = { view: "skills", selected: null, data: null, options: null };
let ctx; // { openCompare(a, b) } supplied by app.js

export async function init(appCtx) {
  ctx = appCtx;
  state.options = await api.options();
  const sw = document.getElementById("view-switch");
  sw.innerHTML = Object.entries(state.options.views).map(([k, v]) =>
    `<button type="button" role="radio" data-view="${k}" aria-checked="${k === state.view}">${esc(v.label)}</button>`).join("");
  sw.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-view]");
    if (b) setView(b.dataset.view);
  });
  await setView(state.view);
  await select("Data Scientist");
}

async function setView(view) {
  state.view = view;
  document.querySelectorAll("#view-switch button").forEach((b) => b.setAttribute("aria-checked", b.dataset.view === view));
  state.data = await api.similarity(view);
  const v = state.options.views[view];
  document.getElementById("view-note").textContent = `${v.metric}. ${v.range}.`;
  redraw();
  if (state.selected) renderPanel(state.selected);
}

export function redraw() {
  if (!state.data) return;
  drawMap();
  drawHeatmap();
  drawDendrogram();
}

function stressWord(s) {
  return s < 0.1 ? "good" : s < 0.2 ? "fair" : "rough";
}

function drawMap() {
  const d = state.data, t = tokens();
  const xs = d.xy.map((p) => p[0]), ys = d.xy.map((p) => p[1]);
  const sel = state.selected ? d.roles.indexOf(state.selected) : -1;
  const near = sel >= 0
    ? d.matrix[sel].map((v, j) => [v, j]).filter(([, j]) => j !== sel).sort((a, b) => a[0] - b[0]).slice(0, 4).map(([, j]) => j)
    : [];
  const lit = (i) => sel < 0 || i === sel || near.includes(i);
  const size = (i) => 10 + Math.sqrt(d.n[i]) / 1.6;
  const traces = [];

  // lines from the selected role to its nearest neighbours (drawn first so dots sit on top)
  near.forEach((j) => traces.push({
    type: "scatter", mode: "lines", x: [xs[sel], xs[j]], y: [ys[sel], ys[j]], hoverinfo: "skip",
    line: { color: t.ink3, width: 1.5 }, showlegend: false,
  }));
  for (const [g, name, color] of [["data", "Data roles", t.s1], ["adjacent", "Adjacent roles", t.s2]]) {
    const idx = d.roles.map((_, i) => i).filter((i) => d.groups[i] === g);
    traces.push({
      type: "scatter", mode: "markers", name, x: idx.map((i) => xs[i]), y: idx.map((i) => ys[i]),
      customdata: idx.map((i) => [d.roles[i], d.n[i], d.band_mean[i], d.clusters[i]]),
      marker: {
        color, size: idx.map(size), opacity: idx.map((i) => (lit(i) ? 1 : 0.35)),
        line: { color: idx.map((i) => (i === sel ? t.ink : t.surface)), width: idx.map((i) => (i === sel ? 3 : 2)) },
      },
      hovertemplate: "<b>%{customdata[0]}</b><br>%{customdata[1]} postings<br>mean band %{customdata[2]:.2f}<br>cluster %{customdata[3]}<extra></extra>",
      cliponaxis: false,
    });
  }
  const pad = (arr, f) => { const lo = Math.min(...arr), hi = Math.max(...arr), r = (hi - lo) || 1; return [lo - r * f, hi + r * f]; };
  const el = document.getElementById("atlas-map");
  const narrow = el.clientWidth < 600; // phones: let the map stretch instead of keeping a square aspect
  plot(el, traces, {
    showlegend: true, legend: { x: 0, y: 1.02 },
    xaxis: { visible: false, range: pad(xs, narrow ? 0.15 : 0.3) },
    yaxis: { visible: false, range: pad(ys, 0.12), ...(narrow ? {} : { scaleanchor: "x" }) },
    margin: { l: 4, r: 4, t: 30, b: 4 }, hovermode: "closest",
  }).then(() => placeLabels(el, xs, ys, size, lit, sel, near));

  el.removeAllListeners?.("plotly_click");
  el.on("plotly_click", (ev) => {
    const p = ev.points[0];
    if (p?.customdata) select(p.customdata[0]);
  });
  document.getElementById("map-caption").textContent =
    `The axes have no units; only the gaps between dots matter. Dot size shows the number of postings; numbers in brackets are distances from the selected role. ` +
    `Map fit is ${stressWord(d.stress1)} (stress ${d.stress1}), so treat it as a sketch and read exact values from the heatmap.`;
}

// Greedy label placement: try 8 spots around each dot and keep the one that overlaps least
// with dots and labels already placed. Selected and neighbouring roles are placed first.
function placeLabels(el, xs, ys, size, lit, sel, near) {
  const d = state.data, t = tokens();
  const fl = el._fullLayout;
  if (!fl?.xaxis?.l2p) return;
  const X = (v) => fl.xaxis.l2p(v), Y = (v) => fl.yaxis.l2p(v);
  const W = fl.xaxis._length, H = fl.yaxis._length;
  const boxes = d.roles.map((_, i) => { const r = size(i) / 2; return [X(xs[i]) - r, Y(ys[i]) - r, X(xs[i]) + r, Y(ys[i]) + r]; });
  const overlap = (a, b) => Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const order = d.roles.map((_, i) => i).sort((a, b) => (lit(b) - lit(a)) || (d.n[b] - d.n[a]));
  if (sel >= 0) order.splice(order.indexOf(sel), 1), order.unshift(sel);
  const placed = [], annotations = [];
  const narrow = W < 560;
  for (const i of order) {
    if (narrow && sel >= 0 && !lit(i)) continue; // on phones only label the selected role and its neighbours
    const label = near.includes(i) ? `${d.roles[i]} (${d.matrix[sel][i].toFixed(2)})` : d.roles[i];
    const w = label.length * 6.4 + 6, h = 16, r = size(i) / 2 + 4, px = X(xs[i]), py = Y(ys[i]);
    const spots = [
      [px + r, py - h / 2, "left", "middle"], [px - r - w, py - h / 2, "right", "middle"],
      [px - w / 2, py - r - h, "center", "bottom"], [px - w / 2, py + r, "center", "top"],
      [px + r * 0.7, py - r - h * 0.8, "left", "bottom"], [px - r * 0.7 - w, py - r - h * 0.8, "right", "bottom"],
      [px + r * 0.7, py + r * 0.8, "left", "top"], [px - r * 0.7 - w, py + r * 0.8, "right", "top"],
    ];
    let best = null;
    for (const [x0, y0, xa, ya] of spots) {
      const box = [x0, y0, x0 + w, y0 + h];
      let cost = [...placed, ...boxes.filter((_, k) => k !== i)].reduce((s, b) => s + overlap(box, b), 0);
      if (x0 < 0 || x0 + w > W || y0 < 0 || y0 + h > H) cost += 5000;
      if (!best || cost < best.cost) best = { cost, box, xa, ya };
    }
    placed.push(best.box);
    const shift = { left: r, right: -r, center: 0 }[best.xa] * (best.ya === "middle" ? 1 : 0.7);
    const vshift = { middle: 0, bottom: r, top: -r }[best.ya] * (best.xa === "center" ? 1 : 0.8);
    annotations.push({
      x: xs[i], y: ys[i], text: label, showarrow: false, xanchor: best.xa, yanchor: best.ya,
      xshift: shift, yshift: vshift,
      font: { size: 12, color: lit(i) ? t.ink : t.ink3, family: "Archivo, system-ui, sans-serif" },
    });
  }
  Plotly.relayout(el, { annotations });
}

function drawHeatmap() {
  const d = state.data, t = tokens();
  const order = d.order.map((r) => d.roles.indexOf(r));
  const z = order.map((i) => order.map((j) => (i === j ? null : d.matrix[i][j])));
  const max = Math.max(...z.flat().filter((v) => v != null));
  plot("atlas-heatmap", [{
    type: "heatmap", x: d.order, y: d.order, z, zmin: 0, zmax: max, colorscale: seqScale(true),
    xgap: 2, ygap: 2, hovertemplate: "%{y}<br>%{x}<br>distance %{z:.3f}<extra></extra>",
    colorbar: { thickness: 10, outlinewidth: 0, tickfont: { color: t.ink3, size: 10 }, title: { text: "distance", font: { size: 11 } } },
  }], {
    xaxis: { tickangle: -50, showgrid: false, tickfont: { size: 10 } },
    yaxis: { autorange: "reversed", showgrid: false, tickfont: { size: 10 } },
    margin: { l: 10, r: 10, t: 10, b: 10 },
  });
  const el = document.getElementById("atlas-heatmap");
  el.removeAllListeners?.("plotly_click");
  el.on("plotly_click", (ev) => {
    const p = ev.points[0];
    if (p && p.x !== p.y) ctx.openCompare(p.y, p.x);
  });
}

function drawDendrogram() {
  const d = state.data, t = tokens();
  const dn = d.dendrogram;
  const traces = dn.icoord.map((ys, k) => ({
    type: "scatter", mode: "lines", x: dn.dcoord[k], y: ys, hoverinfo: "skip",
    line: { color: t.ink3, width: 1.5 },
  }));
  const leafY = dn.ivl.map((_, i) => 5 + 10 * i);
  const cl = dn.ivl.map((r) => d.clusters[d.roles.indexOf(r)]);
  traces.push({
    type: "scatter", mode: "markers", x: dn.ivl.map(() => 0), y: leafY,
    marker: { size: 11, color: cl.map((c) => t.clusters[(c - 1) % 5]), line: { color: t.surface, width: 2 } },
    customdata: dn.ivl.map((r, i) => [r, cl[i]]),
    hovertemplate: "%{customdata[0]}<br>cluster %{customdata[1]}<extra></extra>",
  });
  plot("atlas-dendro", traces, {
    xaxis: { title: { text: "distance at which branches join" }, rangemode: "tozero" },
    yaxis: { tickvals: leafY, ticktext: dn.ivl, autorange: "reversed", showgrid: false, zeroline: false, tickfont: { size: 11, color: t.ink2 } },
    margin: { l: 10, r: 16, t: 10, b: 10 },
  });
}

async function select(role) {
  state.selected = role;
  drawMap();
  await renderPanel(role);
}

async function renderPanel(role) {
  const p = await api.profile(role);
  const fams = state.options.families;
  const labels = state.options.family_labels;
  const near = p.nearest[state.view];
  const ds = p.dsjobs;
  const panel = document.getElementById("role-panel");
  panel.innerHTML = `
    <h3>${esc(p.role)}</h3>
    <p class="group-tag">${p.group === "data" ? "Data role" : "Adjacent role"}, ${p.n.toLocaleString()} postings</p>
    <dl class="facts">
      <div><dt>Typical band</dt><dd>${esc(p.band_median)} L</dd></div>
      <div><dt>Mean min. experience</dt><dd>${p.exp_min_mean} yrs</dd></div>
      <div><dt>Senior titles</dt><dd>${pct(p.senior_share)}</dd></div>
      <div><dt>Advertised average</dt><dd>${ds ? `${ds.avg_salary_lakhs} L` : "–"}</dd></div>
    </dl>
    <h4>Competencies asked for</h4>
    <ul class="bar-list">${fams.map((f) => bar(labels[f], p.family_prevalence[f])).join("")}</ul>
    <h4>Most listed skills</h4>
    <ul class="bar-list">${p.top_skills.slice(0, 6).map((s) => bar(s.skill, s.prevalence)).join("")}</ul>
    <h4>Nearest roles in this view</h4>
    <ul class="neighbours">${near.map((n) =>
      `<li><button type="button" data-role="${esc(n.role)}">${esc(n.role)}</button><span>${n.distance.toFixed(3)}</span></li>`).join("")}</ul>
    <button type="button" class="link-btn" id="cmp-nearest">Compare with ${esc(near[0].role)}</button>
    <p class="hint" style="margin-top:12px">Example titles: ${p.example_titles.slice(0, 4).map(esc).join("; ")}</p>`;
  panel.querySelectorAll(".neighbours button").forEach((b) => b.addEventListener("click", () => select(b.dataset.role)));
  panel.querySelector("#cmp-nearest").addEventListener("click", () => ctx.openCompare(role, near[0].role));
}

function bar(label, v) {
  return `<li><span class="bar" style="--w:${Math.max(1, v * 100).toFixed(1)}%">${esc(label)}</span><span class="num">${pct(v)}</span></li>`;
}
