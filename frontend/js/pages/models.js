// models.js - phase 3 results: model comparison, ROC, coefficients, confusion matrix, top terms.
import { api } from "../api.js";
import { divergingBars, esc, plot, pretty, seqScale, table, tokens } from "../charts.js";

let M = null;
let termBlock = "skills";
const TERM_LABELS = { skills: "Skills", title: "Job-title words", city: "Cities", family: "Competency flags" };

export async function init() {
  M = await api.models();
  const sw = document.getElementById("md-term-switch");
  sw.innerHTML = Object.entries(TERM_LABELS).map(([k, v]) =>
    `<button type="button" role="radio" data-k="${k}" aria-checked="${k === termBlock}">${v}</button>`).join("");
  sw.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-k]");
    if (!b) return;
    termBlock = b.dataset.k;
    sw.querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", x.dataset.k === termBlock));
    drawTerms();
  });
  redraw();
}

function binaryTable(el, m) {
  const rows = m.comparison.map((c) => [esc(c.model), `${c.auc.toFixed(3)} ± ${c.auc_sd.toFixed(3)}`,
    c.accuracy.toFixed(3), c.f1.toFixed(3), c.brier.toFixed(3)]);
  const chosen = m.comparison.findIndex((c) => c.model === m.chosen);
  document.getElementById(el).innerHTML =
    `<p class="hint">n = ${m.n}, ${Math.round(m.positive_rate * 100)}% in the high group. Mean of 50 cross-validation folds.</p>` +
    table(["Model", "AUC", "Accuracy", "F1", "Brier"], rows, { numeric: [1, 2, 3, 4], chosen }) +
    `<p class="reason">Kept: ${esc(m.chosen)}, because ${esc(m.reason)}.</p>`;
}

export function redraw() {
  if (!M) return;
  const t = tokens();
  binaryTable("md-jds-table", M.jds);
  binaryTable("md-sds-table", M.sds);

  plot("md-roc", [
    { type: "scatter", mode: "lines", x: [0, 1], y: [0, 1], line: { color: t.rule, width: 1 }, hoverinfo: "skip", showlegend: false },
    { type: "scatter", mode: "lines", name: `Salary hike (AUC ${M.jds.oof_auc})`, x: M.jds.roc.fpr, y: M.jds.roc.tpr,
      line: { color: t.s1, width: 2, shape: "hv" }, hovertemplate: "false positive %{x:.2f}<br>true positive %{y:.2f}<extra></extra>" },
    { type: "scatter", mode: "lines", name: `Success (AUC ${M.sds.oof_auc})`, x: M.sds.roc.fpr, y: M.sds.roc.tpr,
      line: { color: t.s2, width: 2, shape: "hv" }, hovertemplate: "false positive %{x:.2f}<br>true positive %{y:.2f}<extra></extra>" },
  ], { showlegend: true, xaxis: { title: { text: "false positive rate" }, range: [0, 1] },
       yaxis: { title: { text: "true positive rate" }, range: [0, 1.02] } });

  const coefRows = [...M.jds.coefficients.map((c) => ({ ...c, m: "Salary hike" })),
                    ...M.sds.coefficients.map((c) => ({ ...c, m: "Success" }))];
  const mk = (name, color) => {
    const r = coefRows.filter((c) => c.m === name);
    return {
      type: "scatter", mode: "markers", name, x: r.map((c) => c.coef_std), y: r.map((c) => pretty(c.feature)),
      error_x: { type: "data", symmetric: false, array: r.map((c) => c.ci_high - c.coef_std),
                 arrayminus: r.map((c) => c.coef_std - c.ci_low), color: t.ink3, thickness: 1.5, width: 0 },
      marker: { color, size: 11, line: { color: t.surface, width: 2 } },
      customdata: r.map((c) => c.odds_ratio_per_sd),
      hovertemplate: "%{y}<br>coefficient %{x:.2f}<br>odds x%{customdata} per 1 sd<extra></extra>",
    };
  };
  plot("md-coef", [mk("Salary hike", t.s1), mk("Success", t.s2)], {
    showlegend: true, xaxis: { title: { text: "change in log-odds per 1 standard deviation" }, zeroline: true, zerolinecolor: t.ink3 },
    yaxis: { autorange: "reversed", gridcolor: t.grid },
  });

  const b = M.band;
  const chosen = b.comparison.findIndex((c) => c.model === b.chosen);
  document.getElementById("md-band-table").innerHTML =
    `<p class="hint">${b.n_train.toLocaleString()} training and ${b.n_test.toLocaleString()} test postings. ${esc(b.split)}. Regularisation C = ${b.best_C}.</p>` +
    table(["Model", "Exact band", "Within 1 band", "Mean error (bands)", "Weighted kappa"],
      b.comparison.map((c) => [esc(c.model), c.accuracy.toFixed(3), c.within_one_band.toFixed(3), c.mae_bands.toFixed(3), c.qwk.toFixed(3)]),
      { numeric: [1, 2, 3, 4], chosen }) +
    `<p class="reason">The ordinal model treats bands as ordered (3–6 is closer to 6–10 than to 25–50), so its mistakes are smaller.</p>`;

  const cm = b.confusion_matrix;
  const rowPct = cm.map((r) => { const s = r.reduce((a, v) => a + v, 0) || 1; return r.map((v) => v / s); });
  plot("md-cm", [{
    type: "heatmap", x: b.bands, y: b.bands, z: rowPct, zmin: 0, zmax: 1, colorscale: seqScale(false),
    text: cm.map((r) => r.map(String)), texttemplate: "%{text}", textfont: { size: 11 },
    xgap: 2, ygap: 2, showscale: false,
    hovertemplate: "true %{y}, predicted %{x}<br>%{text} postings (%{z:.0%} of the row)<extra></extra>",
  }], { xaxis: { title: { text: "predicted band" }, showgrid: false }, yaxis: { title: { text: "true band" }, autorange: "reversed", showgrid: false } });

  drawTerms();
}

function drawTerms() {
  const blk = M.band.top_terms[termBlock];
  const clean = (l) => l.replace(/^city_primary_/, "").replace(/^has_/, "").replace(/_sklearn$/, "");
  const rows = [...blk.raises_band, ...[...blk.lowers_band].reverse()];
  divergingBars("md-terms", rows.map((r) => clean(r.label)), rows.map((r) => r.coef), {
    title: "average ordinal coefficient (positive = higher band, holding everything else fixed)",
    hover: "%{y}<br>coefficient %{x:+.3f}<extra></extra>",
  });
}
