// compare.js - two roles side by side, in plain language.
import { api } from "../api.js";
import { esc, fmtBand, fmtP, isRealSkill, plot, shortBand, table, tokens } from "../charts.js";

let last = null;
const $ = (id) => document.getElementById(id);

export async function init() {
  const opts = await api.options();
  const html = opts.roles.map((r) => `<option>${esc(r)}</option>`).join("");
  $("cmp-a").innerHTML = html;
  $("cmp-b").innerHTML = html;
  $("cmp-a").value = "Data Scientist";
  $("cmp-b").value = "Data Analyst";
  $("cmp-a").addEventListener("change", run);
  $("cmp-b").addEventListener("change", run);
  $("cmp-swap").addEventListener("click", () => { [$("cmp-a").value, $("cmp-b").value] = [$("cmp-b").value, $("cmp-a").value]; run(); });
  await run();
}

export async function show(a, b) {
  $("cmp-a").value = a;
  $("cmp-b").value = b;
  await run();
}

async function alike(view, a, b) {
  const s = await api.similarity(view);
  const i = s.roles.indexOf(a), j = s.roles.indexOf(b);
  const max = Math.max(...s.matrix.flat()) || 1;
  return 1 - s.matrix[i][j] / max;
}

async function run() {
  const a = $("cmp-a").value, b = $("cmp-b").value;
  if (a === b) {
    $("cmp-summary").innerHTML = `<div class="card"><p class="empty">Pick two different roles.</p></div>`;
    return;
  }
  const [d, skills, overall, pay] = await Promise.all([api.compare(a, b), alike("skills", a, b), alike("blended", a, b), alike("salary", a, b)]);
  last = { d, skills, overall, pay };
  redraw();
}

export function redraw() {
  if (!last) return;
  const { d, skills, overall, pay } = last;
  const t = tokens();
  const A = d.a, B = d.b;
  const pct = (v) => `${Math.round(v * 100)}%`;
  const verdict = skills >= 0.6 ? "very similar jobs" : skills >= 0.35 ? "related jobs with a fair amount in common" : "quite different jobs";
  const roleCard = (p, cls) => `
    <div class="cmp-role ${cls}">
      <h3>${esc(p.role)}</h3>
      <dl class="facts">
        <div><dt>Typical pay</dt><dd>${fmtBand(p.band_median)}</dd></div>
        <div><dt>Usual experience</dt><dd>${p.exp_min_median}+ yrs</dd></div>
        <div><dt>Job postings</dt><dd>${p.n.toLocaleString()}</dd></div>
        <div><dt>Advertised average</dt><dd>${p.dsjobs ? `₹${p.dsjobs.avg_salary_lakhs} LPA` : "–"}</dd></div>
      </dl>
    </div>`;
  $("cmp-summary").innerHTML = `
    <div class="cmp-hero">
      <span class="big">${pct(skills)}</span>
      <p>alike in skills. <strong>${esc(A.role)}</strong> and <strong>${esc(B.role)}</strong> are ${verdict}.
        Pay is ${pct(pay)} alike, and ${pct(overall)} alike overall.</p>
    </div>
    ${roleCard(A, "a")}${roleCard(B, "b")}`;

  const top = (p) => p.top_skills.map((s) => s.skill).filter(isRealSkill).slice(0, 12);
  const sa = top(A), sb = top(B);
  const both = sa.filter((s) => sb.includes(s));
  const onlyA = sa.filter((s) => !sb.includes(s));
  const onlyB = sb.filter((s) => !sa.includes(s));
  const chips = (arr, cls) => arr.length ? `<ul class="chips">${arr.map((s) => `<li class="chip ${cls}">${esc(s)}</li>`).join("")}</ul>` : `<p class="muted">None among the top skills.</p>`;
  $("cmp-skills").innerHTML = `
    <div class="card"><h3>Only ${esc(A.role)} asks for</h3>${chips(onlyA, "")}</div>
    <div class="card"><h3>Both ask for</h3>${chips(both, "have")}</div>
    <div class="card"><h3>Only ${esc(B.role)} asks for</h3>${chips(onlyB, "")}</div>`;

  const fams = d.families, labels = fams.map((f) => d.family_labels[f]);
  const pair = (fa, fb, extra) => [
    { type: "bar", name: A.role, marker: { color: t.s1 }, ...fa, ...extra },
    { type: "bar", name: B.role, marker: { color: t.s2 }, ...fb, ...extra },
  ];
  plot("cmp-fam", pair(
    { y: labels, x: fams.map((f) => A.family_prevalence[f]) },
    { y: labels, x: fams.map((f) => B.family_prevalence[f]) },
    { orientation: "h", hovertemplate: "%{fullData.name}<br>%{y}: %{x:.0%}<extra></extra>" }),
    { showlegend: true, barmode: "group", bargap: 0.3, bargroupgap: 0.08, xaxis: { tickformat: ".0%" },
      yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" } });
  plot("cmp-band", pair(
    { x: d.bands.map(shortBand), y: A.band_distribution }, { x: d.bands.map(shortBand), y: B.band_distribution },
    { hovertemplate: "%{fullData.name}<br>%{x}: %{y:.0%}<extra></extra>" }),
    { showlegend: true, barmode: "group", bargap: 0.3, bargroupgap: 0.08, yaxis: { tickformat: ".0%" },
      xaxis: { gridcolor: "rgba(0,0,0,0)" } });

  const tst = d.test;
  const sig = (p) => (p < 0.05 ? "yes" : "no");
  const signed = (v) => (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2));
  $("cmp-tests").innerHTML = `
    <p class="muted">Differences are ${esc(A.role)} minus ${esc(B.role)}. p-values are Holm-corrected across all 171 role pairs.</p>
    ${table(["Measure", "Difference", "Test", "Holm p", "Significant"], [
      ["Skill mix", `distance ${tst.skill_cosine_distance.toFixed(3)}`, `permutation z = ${tst.skill_perm_z}`, fmtP(tst.skill_perm_holm_p), sig(tst.skill_perm_holm_p)],
      ["Salary band", `${signed(tst.band_diff)} bands`, "Mann-Whitney U", fmtP(tst.band_mwu_holm_p), sig(tst.band_mwu_holm_p)],
      ["Min. experience", `${signed(tst.exp_diff)} yrs`, "Mann-Whitney U", fmtP(tst.exp_mwu_holm_p), sig(tst.exp_mwu_holm_p)],
    ], { numeric: [3] })}
    <p class="muted" style="margin-top:10px">Top-20 skill overlap (Jaccard): ${d.jaccard_top20}.</p>`;
}
