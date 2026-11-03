// charts.js - shared Plotly helpers so every chart follows the same theme and rules:
// thin marks, hairline grid, one axis, legends only when there are two or more series.

const PRETTY = {
  big_data_skills: "Big data", maths_stats_skills: "Maths & stats", coding_skills: "Coding",
  ai_and_ml_skills: "AI & ML", dashboard_and_storytelling_skills: "Dashboards & storytelling",
  neuroticism: "Neuroticism", extraversion: "Extraversion", openness_to_experience: "Openness",
  agreeableness: "Agreeableness", conscientiousness: "Conscientiousness",
  big_data: "Big data", maths_stats: "Maths & stats", coding: "Coding", ai_ml: "AI & ML", dashboards: "Dashboards",
};
export const pretty = (k) => PRETTY[k] ?? k;

// Read the colour tokens from styles.css so charts switch with the light/dark theme.
export function tokens() {
  const cs = getComputedStyle(document.documentElement);
  const g = (n) => cs.getPropertyValue(n).trim();
  return {
    page: g("--page"), surface: g("--surface"), surface2: g("--surface-2"),
    ink: g("--ink"), ink2: g("--ink-2"), ink3: g("--ink-3"), rule: g("--rule"), grid: g("--grid"),
    accent: g("--accent"), s1: g("--series-1"), s2: g("--series-2"), pos: g("--pos"), neg: g("--neg"), mid: g("--mid"),
    seq: [0, 1, 2, 3, 4, 5].map((i) => g(`--seq-${i}`)),
    clusters: [1, 2, 3, 4, 5].map((i) => g(`--cl-${i}`)),
  };
}

function merge(base, extra) {
  const out = { ...base };
  for (const [k, v] of Object.entries(extra || {})) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) && base[k] && typeof base[k] === "object"
      ? merge(base[k], v) : v;
  }
  return out;
}

export function layout(extra = {}) {
  const t = tokens();
  const axis = {
    gridcolor: t.grid, linecolor: t.rule, zerolinecolor: t.rule, zerolinewidth: 1,
    tickfont: { color: t.ink3, size: 11 }, title: { font: { color: t.ink2, size: 12 } }, automargin: true,
  };
  return merge({
    paper_bgcolor: t.surface, plot_bgcolor: t.surface,
    font: { family: "Archivo, system-ui, sans-serif", color: t.ink2, size: 12 },
    margin: { l: 10, r: 16, t: 12, b: 10 },
    xaxis: axis, yaxis: axis, showlegend: false,
    legend: { orientation: "h", x: 0, y: 1.12, font: { color: t.ink2 } },
    hoverlabel: { bgcolor: t.surface, bordercolor: t.rule, font: { color: t.ink, family: "Archivo, system-ui, sans-serif" } },
    bargap: 0.35,
  }, extra);
}

export const config = {
  responsive: true, displaylogo: false,
  modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
  toImageButtonOptions: { format: "png", scale: 2 },
};

export function plot(el, data, lay = {}, extraConfig = {}) {
  const node = typeof el === "string" ? document.getElementById(el) : el;
  return Plotly.react(node, data, layout(lay), { ...config, ...extraConfig });
}

// Sequential colour scale (light -> dark). reverse=true makes SMALL values dark (for distances).
export function seqScale(reverse = false) {
  const s = tokens().seq;
  const stops = [0, 0.15, 0.35, 0.6, 0.82, 1];
  const cols = reverse ? [...s].reverse() : s;
  return stops.map((p, i) => [p, cols[i]]);
}

// Horizontal bars where sign matters (positive = pos colour, negative = neg colour).
export function divergingBars(el, labels, values, { hover, title = "", height, text } = {}) {
  const t = tokens();
  return plot(el, [{
    type: "bar", orientation: "h", y: labels, x: values,
    marker: { color: values.map((v) => (v >= 0 ? t.pos : t.neg)) },
    hovertemplate: hover ?? "%{y}: %{x:.3f}<extra></extra>",
    text, textposition: "outside", textfont: { color: t.ink2, size: 11 }, cliponaxis: false,
  }], {
    xaxis: { title: { text: title }, zeroline: true, zerolinecolor: t.ink3 },
    yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" },
    margin: { l: 10, r: 40, t: 8, b: 10 }, ...(height ? { height } : {}),
  });
}

export const fmtP = (p) => (p == null ? "–" : p < 0.001 ? "< 0.001" : p.toFixed(3));
export const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function table(headers, rows, { numeric = [], chosen } = {}) {
  const th = headers.map((h, i) => `<th class="${numeric.includes(i) ? "n" : ""}">${esc(h)}</th>`).join("");
  const tr = rows.map((r, ri) => `<tr class="${chosen === ri ? "chosen" : ""}">${r.map((c, i) =>
    `<td class="${numeric.includes(i) ? "n" : ""}">${c}</td>`).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
}
