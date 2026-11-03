// stats.js - phase 2 results: effect sizes, market premiums, alignment.
import { api } from "../api.js";
import { divergingBars, fmtP, plot, pretty, tokens } from "../charts.js";

let S = null;

export async function init() {
  S = await api.stats();
  redraw();
}

function forest(el, rows) {
  const t = tokens();
  const y = rows.map((r) => pretty(r.feature));
  plot(el, [{
    type: "scatter", mode: "markers", x: rows.map((r) => r.cohens_d), y,
    error_x: { type: "data", symmetric: false, array: rows.map((r) => r.ci_high - r.cohens_d),
               arrayminus: rows.map((r) => r.cohens_d - r.ci_low), color: t.ink3, thickness: 1.5, width: 0 },
    marker: { size: 12, color: t.s1, symbol: rows.map((r) => (r.significant ? "circle" : "circle-open")), line: { width: 2, color: t.s1 } },
    customdata: rows.map((r) => [r.test, fmtP(r.holm_p), r.mean_low, r.mean_high]),
    hovertemplate: "<b>%{y}</b><br>d = %{x:.2f}<br>%{customdata[0]}, Holm p %{customdata[1]}<br>mean low %{customdata[2]} vs high %{customdata[3]}<extra></extra>",
  }], {
    xaxis: { title: { text: "Cohen's d (high group minus low group)" }, zeroline: true, zerolinecolor: t.ink3 },
    yaxis: { autorange: "reversed", gridcolor: t.grid },
  });
}

export function redraw() {
  if (!S) return;
  const t = tokens();
  forest("st-jds", S.jds);
  forest("st-sds", S.sds);

  const fam = [...S.market.family_vs_band].sort((a, b) => b.band_diff - a.band_diff);
  divergingBars("st-fam", fam.map((r) => `${pretty(r.family)} (${Math.round(r.pct_postings)}% of postings)`),
    fam.map((r) => r.band_diff), { title: "salary-band difference (bands)", hover: "%{y}<br>%{x:+.2f} bands<extra></extra>" });

  const eb = S.market.experience_by_band;
  const bands = ["0to3", "3to6", "6to10", "10to15", "15to25", "25to50"];
  plot("st-exp", [{
    type: "bar", x: eb.map((r) => bands[r.band]), y: eb.map((r) => r.mean), marker: { color: t.s1 },
    customdata: eb.map((r) => [r.count, r.median, r.std]),
    hovertemplate: "%{x} lakhs<br>mean %{y:.1f} yrs, median %{customdata[1]}<br>sd %{customdata[2]}, n %{customdata[0]}<extra></extra>",
  }], { xaxis: { title: { text: "salary band (lakhs per year)" }, gridcolor: "rgba(0,0,0,0)" },
        yaxis: { title: { text: "years of experience" } } });

  const bd = S.market.big_data_by_experience;
  plot("st-bigdata", [{
    type: "bar", x: bd.map((r) => `${r.stratum} yrs`), y: bd.map((r) => r.band_diff), marker: { color: t.s1 },
    customdata: bd.map((r) => [r.n_with, r.n_without, fmtP(r.p)]),
    hovertemplate: "%{x}<br>%{y:+.2f} bands<br>with %{customdata[0]}, without %{customdata[1]}<br>p %{customdata[2]}<extra></extra>",
  }], { xaxis: { title: { text: "minimum experience asked for" }, gridcolor: "rgba(0,0,0,0)" },
        yaxis: { title: { text: "band premium for big data" } } });

  const al = S.alignment;
  document.getElementById("st-align-note").textContent =
    `Each dot is a competency. Spearman rho = ${al.spearman_rho} (n = ${al.n_families}, p = ${al.p}). ${al.note}`;
  plot("st-align", [{
    type: "scatter", mode: "markers+text", x: al.table.map((r) => r.internal_d), y: al.table.map((r) => r.market_band_diff),
    text: al.table.map((r) => pretty(r.family)), textposition: "top center", textfont: { color: t.ink2 },
    marker: { size: 12, color: t.s1, line: { color: t.surface, width: 2 } }, cliponaxis: false,
    hovertemplate: "%{text}<br>internal d %{x:.2f}<br>market %{y:+.2f} bands<extra></extra>",
  }], { xaxis: { title: { text: "effect on salary hike inside the company (d)" } },
        yaxis: { title: { text: "market pay premium (bands)" }, zeroline: true, zerolinecolor: t.ink3 },
        margin: { t: 24 } });

  const sk = S.market.top_skills_vs_band;
  const t2 = tokens();
  plot("st-skills", [{
    type: "bar", orientation: "h", y: sk.map((r) => r.skill), x: sk.map((r) => r.band_diff),
    marker: { color: sk.map((r) => (r.band_diff >= 0 ? t2.pos : t2.neg)), opacity: sk.map((r) => (r.significant ? 1 : 0.4)) },
    customdata: sk.map((r) => [r.postings, fmtP(r.holm_p)]),
    hovertemplate: "%{y}<br>%{x:+.2f} bands<br>%{customdata[0]} postings, Holm p %{customdata[1]}<extra></extra>",
  }], { xaxis: { title: { text: "band difference, with vs without the skill (faded = not significant)" },
                 zeroline: true, zerolinecolor: t2.ink3 },
        yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" } });
}
