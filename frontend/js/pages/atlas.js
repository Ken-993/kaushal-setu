// atlas.js - analyst view: the full distance heatmap and the dendrogram, for five definitions of "alike".
import { api } from "../api.js";
import { esc, plot, seqScale, tokens } from "../charts.js";

const state = { view: "skills", data: null, options: null };
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
}

async function setView(view) {
  state.view = view;
  document.querySelectorAll("#view-switch button").forEach((b) => b.setAttribute("aria-checked", b.dataset.view === view));
  state.data = await api.similarity(view);
  const v = state.options.views[view];
  document.getElementById("view-note").textContent = `${v.metric}. ${v.range}.`;
  redraw();
}

export function redraw() {
  if (!state.data) return;
  drawHeatmap();
  drawDendrogram();
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

