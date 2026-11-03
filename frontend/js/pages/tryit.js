// tryit.js - live predictions: sliders -> POST to the API -> charts update.
import { api } from "../api.js";
import { divergingBars, esc, pct, plot, pretty, table, tokens } from "../charts.js";

let opts, lastMatch, lastSds, lastBand;
const skills = new Set(["python", "sql", "machine learning"]);

function debounce(fn, ms = 180) {
  let id;
  return (...a) => { clearTimeout(id); id = setTimeout(() => fn(...a), ms); };
}

function sliders(formId, info, { min, max, step, start = {} }) {
  const form = document.getElementById(formId);
  form.innerHTML = info.features.map((f) => {
    const avg = info.feature_means[f];
    const init = start[f] ?? avg;
    const v = step < 1 ? init.toFixed(1) : Math.round(init);
    return `<div class="slider"><label for="${formId}-${f}">${pretty(f)} <output id="${formId}-${f}-out">${v}</output>
      <input type="range" id="${formId}-${f}" name="${f}" min="${min}" max="${max}" step="${step}" value="${v}">
      <span class="avg">company average ${avg.toFixed(step < 1 ? 2 : 0)}</span></label></div>`;
  }).join("");
  form.addEventListener("input", (e) => {
    if (e.target.type === "range") document.getElementById(`${e.target.id}-out`).textContent = e.target.value;
  });
  return form;
}

const values = (form) => Object.fromEntries([...new FormData(form)].map(([k, v]) => [k, Number(v)]));

export async function init() {
  opts = await api.options();
  // start from an example junior with clear strengths (maths, AI) so the role fit has a pattern to match
  const sample = { big_data_skills: 3.4, maths_stats_skills: 4.6, coding_skills: 4.2, ai_and_ml_skills: 4.7,
                   dashboard_and_storytelling_skills: 3.9 };
  const jds = sliders("form-jds", opts.jds, { min: 1, max: 5, step: 0.1, start: sample });
  const sds = sliders("form-sds", opts.sds, { min: 15, max: 70, step: 1 });
  const runJ = debounce(async () => { lastMatch = await api.match(values(jds)); drawJds(); });
  const runS = debounce(async () => { lastSds = await api.success(values(sds)); drawSds(); });
  jds.addEventListener("input", runJ);
  sds.addEventListener("input", runS);

  document.getElementById("band-city").innerHTML = opts.cities.map((c) => `<option ${c === "bengaluru" ? "selected" : ""}>${esc(c)}</option>`).join("");
  document.getElementById("skill-list").innerHTML = opts.skills.map((s) => `<option value="${esc(s)}">`).join("");
  const input = document.getElementById("skill-input");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); addSkill(input.value); input.value = ""; }
  });
  input.addEventListener("change", () => { if (opts.skills.includes(input.value.trim().toLowerCase())) { addSkill(input.value); input.value = ""; } });
  document.getElementById("skill-chips").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-skill]");
    if (b) { skills.delete(b.dataset.skill); drawChips(); }
  });
  document.getElementById("form-band").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    lastBand = await api.band({
      exp_min: Number(f.get("exp_min")), exp_max: Number(f.get("exp_max")), job_title: f.get("job_title"),
      city: f.get("city"), skills: [...skills],
    });
    drawBand();
  });
  drawChips();

  lastMatch = await api.match(values(jds));
  lastSds = await api.success(values(sds));
  document.getElementById("form-band").requestSubmit();
  redraw();
}

function addSkill(raw) {
  const s = raw.trim().toLowerCase();
  if (s) { skills.add(s); drawChips(); }
}

function drawChips() {
  document.getElementById("skill-chips").innerHTML = [...skills].map((s) =>
    `<li><button type="button" data-skill="${esc(s)}" aria-label="Remove ${esc(s)}">${esc(s)} ×</button></li>`).join("");
}

export function redraw() { drawJds(); drawSds(); drawBand(); }

function contributions(el, res) {
  const c = res.contributions;
  divergingBars(el, c.map((x) => pretty(x.feature)), c.map((x) => x.log_odds), {
    title: "push on the log-odds vs an average employee",
    hover: "%{y}<br>%{x:+.2f} log-odds<extra></extra>",
  });
}

function drawJds() {
  if (!lastMatch) return;
  const h = lastMatch.hike;
  document.getElementById("jds-prob").textContent = pct(h.probability);
  contributions("jds-contrib", h);
  document.getElementById("jds-note").textContent = `${h.explanation_note} Model: ${h.model}.`;

  const t = tokens();
  const r = lastMatch.ranking;
  if (lastMatch.flat_profile) {
    plot("match-chart", [{
      type: "bar", orientation: "h", y: r.map((x) => x.role), x: r.map((x) => x.coverage_pct), marker: { color: t.s1 },
      hovertemplate: "%{y}<br>coverage %{x}%<extra></extra>",
    }], { xaxis: { title: { text: "coverage of the role's demand (%)" }, range: [0, 100] },
          yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" } });
  } else plot("match-chart", [{
    type: "bar", orientation: "h", y: r.map((x) => x.role), x: r.map((x) => x.similarity),
    marker: { color: r.map((x) => (x.similarity >= 0 ? t.pos : t.neg)) },
    customdata: r.map((x) => [x.coverage_pct, x.band_median]),
    hovertemplate: "%{y}<br>pattern match %{x:+.2f}<br>coverage %{customdata[0]}%<br>typical band %{customdata[1]} L<extra></extra>",
  }], { xaxis: { title: { text: "pattern match (−1 opposite, +1 same shape)" }, range: [-1, 1], zeroline: true, zerolinecolor: t.ink3 },
        yaxis: { autorange: "reversed", gridcolor: "rgba(0,0,0,0)" } });

  const top = r.slice(0, 3).map((x) => [esc(x.role), x.similarity.toFixed(2), `${x.coverage_pct}%`, `${esc(x.band_median)} L`,
    x.skills_to_build.length ? x.skills_to_build.map((g) => esc(g.label)).join(", ") : "nothing major"]);
  document.getElementById("match-gaps").innerHTML = (lastMatch.flat_profile
    ? `<p class="hint">Your scores are evenly balanced, so roles are ranked by coverage only.</p>` : "") +
    table(["Best fits", "Pattern match", "Coverage", "Typical band", "Skills to build"], top, { numeric: [1, 2] });
}

function drawSds() {
  if (!lastSds) return;
  document.getElementById("sds-prob").textContent = pct(lastSds.probability);
  contributions("sds-contrib", lastSds);
  const out = lastSds.outside_training_range;
  document.getElementById("sds-note").textContent = lastSds.explanation_note +
    (out.length ? ` Outside the range seen in training: ${out.map(pretty).join(", ")}, so treat this estimate with care.` : "");
}

function drawBand() {
  if (!lastBand) return;
  const t = tokens();
  document.getElementById("band-pred").textContent = `${lastBand.predicted_band} L`;
  const p = lastBand.probabilities;
  plot("band-chart", [{
    type: "bar", x: p.map((x) => x.band), y: p.map((x) => x.probability), marker: { color: t.s1 },
    hovertemplate: "%{x} lakhs: %{y:.1%}<extra></extra>",
  }], { yaxis: { tickformat: ".0%", rangemode: "tozero" }, xaxis: { title: { text: "salary band (lakhs per year)" }, gridcolor: "rgba(0,0,0,0)" } });
  const fam = lastBand.families_detected.map(pretty).join(", ") || "none";
  const unk = lastBand.unknown_skills;
  document.getElementById("band-note").textContent = `Competencies detected: ${fam}.` +
    (unk.length ? ` Not in the model's vocabulary (ignored): ${unk.join(", ")}.` : "");
}
