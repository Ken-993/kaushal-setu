// insights.js - the plain-language findings plus two headline charts.
import { api } from "../api.js";
import { esc, plot, pretty, shortBand, tokens } from "../charts.js";

let S = null;

export async function init() {
  const [o, s] = await Promise.all([api.overview(), api.stats()]);
  S = s;
  document.getElementById("findings").innerHTML = o.insights.map((i) => `
    <li>
      <p class="area">${esc(i.area)}</p>
      <h3>${esc(i.title)}</h3>
      <p>${esc(i.plain || i.text)}</p>
      ${i.plain ? `<details class="tech"><summary>Technical detail</summary><p>${esc(i.text)}</p><p class="ev">Source: ${esc(i.evidence)}</p></details>` : ""}
    </li>`).join("");
  redraw();
}

export function redraw() {
  if (!S) return;
  const t = tokens();
  const fam = [...S.market.family_vs_band].sort((a, b) => b.band_diff - a.band_diff);
  plot("ins-premium", [{
    type: "bar", orientation: "h", y: fam.map((r) => pretty(r.family)), x: fam.map((r) => r.band_diff),
    marker: { color: fam.map((r) => (r.band_diff >= 0 ? t.pos : t.neg)) },
    text: fam.map((r) => `${r.band_diff > 0 ? "+" : ""}${r.band_diff.toFixed(2)}`), textposition: "outside",
    textfont: { color: t.ink2 }, cliponaxis: false,
    hovertemplate: "%{y}<br>%{x:+.2f} pay ranges higher<extra></extra>",
  }], { xaxis: { title: { text: "pay ranges higher (1 = one step, e.g. ₹6–10L to ₹10–15L)" }, zeroline: true, zerolinecolor: t.ink3 },
        yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" }, margin: { r: 40 } });

  const bands = ["0to3", "3to6", "6to10", "10to15", "15to25", "25to50"];
  const eb = S.market.experience_by_band;
  plot("ins-exp", [{
    type: "bar", x: eb.map((r) => shortBand(bands[r.band])), y: eb.map((r) => r.mean), marker: { color: t.s1 },
    text: eb.map((r) => `${r.mean.toFixed(1)} yrs`), textposition: "outside", textfont: { color: t.ink2 }, cliponaxis: false,
    hovertemplate: "%{x}<br>%{y:.1f} years on average<extra></extra>",
  }], { xaxis: { gridcolor: "rgba(0,0,0,0)" }, yaxis: { title: { text: "years of experience asked for" }, rangemode: "tozero" }, margin: { t: 20 } });
}
