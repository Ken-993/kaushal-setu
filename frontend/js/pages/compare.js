// compare.js - two roles side by side.
import { api } from "../api.js";
import { esc, fmtP, plot, pct, table, tokens } from "../charts.js";

let last = null;

export async function init() {
  const opts = await api.options();
  const a = document.getElementById("cmp-a"), b = document.getElementById("cmp-b");
  const html = opts.roles.map((r) => `<option>${esc(r)}</option>`).join("");
  a.innerHTML = html; b.innerHTML = html;
  a.value = "Data Scientist"; b.value = "Data Analyst";
  a.addEventListener("change", run); b.addEventListener("change", run);
  document.getElementById("cmp-swap").addEventListener("click", () => { [a.value, b.value] = [b.value, a.value]; run(); });
  await run();
}

export async function show(roleA, roleB) {
  document.getElementById("cmp-a").value = roleA;
  document.getElementById("cmp-b").value = roleB;
  await run();
}

async function run() {
  const a = document.getElementById("cmp-a").value, b = document.getElementById("cmp-b").value;
  if (a === b) {
    document.getElementById("cmp-distances").innerHTML = `<div><p class="empty">Pick two different roles.</p></div>`;
    return;
  }
  last = await api.compare(a, b);
  redraw();
}

export function redraw() {
  if (!last) return;
  const d = last, t = tokens();
  const A = d.a.role, B = d.b.role;

  document.getElementById("cmp-distances").innerHTML = Object.values(d.distances).map((v) => `
    <div>
      <div class="k">${esc(v.label)}</div>
      <div class="v">${v.distance.toFixed(3)}</div>
      <div class="meter" aria-hidden="true"><span style="width:${Math.max(2, v.percentile_of_all_pairs)}%"></span></div>
      <div class="r">${ordinal(v.rank_from_a)} closest of ${v.of} to ${esc(A)}; further apart than ${v.percentile_of_all_pairs}% of role pairs</div>
    </div>`).join("");

  const fams = d.families, labels = fams.map((f) => d.family_labels[f]);
  const two = (fa, fb, extra = {}) => [
    { type: "bar", name: A, marker: { color: t.s1 }, ...fa, ...extra },
    { type: "bar", name: B, marker: { color: t.s2 }, ...fb, ...extra },
  ];
  plot("cmp-fam", two(
    { y: labels, x: fams.map((f) => d.a.family_prevalence[f]) },
    { y: labels, x: fams.map((f) => d.b.family_prevalence[f]) },
    { orientation: "h", hovertemplate: "%{fullData.name}<br>%{y}: %{x:.1%}<extra></extra>" }),
    { showlegend: true, barmode: "group", bargap: 0.3, bargroupgap: 0.08, xaxis: { tickformat: ".0%" },
      yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" } });

  plot("cmp-band", two(
    { x: d.bands, y: d.a.band_distribution }, { x: d.bands, y: d.b.band_distribution },
    { hovertemplate: "%{fullData.name}<br>%{x} lakhs: %{y:.1%}<extra></extra>" }),
    { showlegend: true, barmode: "group", bargap: 0.3, bargroupgap: 0.08, yaxis: { tickformat: ".0%" },
      xaxis: { title: { text: "salary band (lakhs per year)" }, gridcolor: "rgba(0,0,0,0)" } });

  const sk = d.skills_side_by_side;
  const gaps = sk.map((s) => ({
    type: "scatter", mode: "lines", x: [s.a, s.b], y: [s.skill, s.skill], hoverinfo: "skip",
    line: { color: t.rule, width: 3 }, showlegend: false,
  }));
  plot("cmp-skills", [
    ...gaps,
    { type: "scatter", mode: "markers", name: A, x: sk.map((s) => s.a), y: sk.map((s) => s.skill),
      marker: { color: t.s1, size: 10, line: { color: t.surface, width: 2 } }, hovertemplate: `${esc(A)}<br>%{y}: %{x:.1%}<extra></extra>` },
    { type: "scatter", mode: "markers", name: B, x: sk.map((s) => s.b), y: sk.map((s) => s.skill),
      marker: { color: t.s2, size: 10, line: { color: t.surface, width: 2 } }, hovertemplate: `${esc(B)}<br>%{y}: %{x:.1%}<extra></extra>` },
  ], { showlegend: true, xaxis: { tickformat: ".0%", rangemode: "tozero" },
       yaxis: { autorange: "reversed", gridcolor: t.grid }, hovermode: "closest" });

  const tst = d.test;
  const sig = (p) => (p < 0.05 ? "yes" : "no");
  const rows = [
    ["Skill mix", `distance ${tst.skill_cosine_distance.toFixed(3)}`, `z = ${tst.skill_perm_z}`, fmtP(tst.skill_perm_holm_p), sig(tst.skill_perm_holm_p)],
    ["Salary band", `${signed(tst.band_diff)} bands`, "Mann-Whitney U", fmtP(tst.band_mwu_holm_p), sig(tst.band_mwu_holm_p)],
    ["Min. experience", `${signed(tst.exp_diff)} yrs`, "Mann-Whitney U", fmtP(tst.exp_mwu_holm_p), sig(tst.exp_mwu_holm_p)],
  ];
  const salary = (p) => (p.dsjobs ? `${p.dsjobs.avg_salary_lakhs} L (${p.dsjobs.postings.toLocaleString()} postings)` : "not in file");
  document.getElementById("cmp-tests").innerHTML = `
    <h3>Are the differences real?</h3>
    <p class="hint">Differences are ${esc(A)} minus ${esc(B)}. p-values are Holm-corrected across all role pairs.</p>
    ${table(["Measure", "Difference", "Test", "Holm p", "Significant"], rows, { numeric: [3] })}
    <h3 style="margin-top:18px">Overlap</h3>
    <p>${Math.round(d.jaccard_top20 * 100)}% of their top-20 skills are shared (Jaccard ${d.jaccard_top20}).</p>
    <p class="hint">${d.shared_top20.length ? `Shared: ${d.shared_top20.map(esc).join(", ")}` : "No shared top-20 skills."}</p>
    <h3 style="margin-top:18px">Advertised salary (DataScience Jobs file)</h3>
    ${table(["Role", "Average", "Typical band (Analytics file)"], [
      [esc(A), salary(d.a), `${esc(d.a.band_median)} L`], [esc(B), salary(d.b), `${esc(d.b.band_median)} L`]])}
    <p class="hint">Postings: ${d.a.n.toLocaleString()} vs ${d.b.n.toLocaleString()}. Senior-title share: ${pct(d.a.senior_share)} vs ${pct(d.b.senior_share)}.</p>`;
}

const signed = (v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2));
function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
