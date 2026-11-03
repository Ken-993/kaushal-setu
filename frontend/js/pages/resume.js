// resume.js - upload a resume -> POST /api/resume -> skills, role fit, salary band.
import { api } from "../api.js";
import { esc, plot, table, tokens } from "../charts.js";

let result = null;   // last /api/resume answer
let band = null;     // last salary-band answer (changes when years or title are edited)

export async function init() {
  const opts = await api.options();
  document.getElementById("resume-city").innerHTML =
    opts.cities.map((c) => `<option ${c === "bengaluru" ? "selected" : ""}>${esc(c)}</option>`).join("");
  document.getElementById("resume-title").innerHTML = opts.roles
    .filter((_, i) => opts.groups[i] === "data").map((r) => `<option>${esc(r)}</option>`).join("");

  const input = document.getElementById("resume-file");
  const drop = document.getElementById("drop");
  const title = document.getElementById("drop-title");
  input.addEventListener("change", () => { title.textContent = input.files[0]?.name ?? "Choose a resume or drop it here"; });
  // drag and drop: hand the dropped file to the hidden <input type="file">
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      title.textContent = input.files[0].name;
    }
  });

  document.getElementById("form-resume").addEventListener("submit", analyse);
  document.getElementById("resume-years").addEventListener("change", reestimate);
  document.getElementById("resume-title").addEventListener("change", reestimate);
}

function setError(msg) {
  let box = document.getElementById("resume-error");
  if (!box) {
    box = document.createElement("p");
    box.id = "resume-error";
    box.className = "status";
    box.setAttribute("role", "alert");
    box.style.margin = "0 0 20px";
    document.getElementById("form-resume").after(box);
  }
  box.textContent = msg || "";
  box.hidden = !msg;
}

async function analyse(e) {
  e.preventDefault();
  const file = document.getElementById("resume-file").files[0];
  if (!file) { setError("Choose a resume file first."); return; }
  const btn = document.getElementById("resume-go");
  btn.disabled = true; btn.textContent = "Reading resume…";
  setError("");
  try {
    result = await api.resume(file, document.getElementById("resume-city").value);
    band = result.salary_band;
    document.getElementById("resume-years").value = result.experience.years;
    document.getElementById("resume-title").value = result.best_data_role;
    document.getElementById("resume-results").hidden = false;
    redraw();
  } catch (err) {
    setError(err.message);
  } finally {
    btn.disabled = false; btn.textContent = "Analyse resume";
  }
}

async function reestimate() {
  if (!result) return;
  const years = Number(document.getElementById("resume-years").value) || 0;
  band = await api.band({
    exp_min: years, exp_max: years + 3, skills: result.skills,
    job_title: document.getElementById("resume-title").value, city: result.city,
  });
  drawBand();
}

export function redraw() {
  if (!result) return;
  const r = result, t = tokens();
  const best = r.ranking[0];
  document.getElementById("resume-summary").innerHTML = [
    ["Skills found", r.skills.length, `${r.skills_known_to_roles.length} of them appear in the role profiles`],
    ["Experience", `${r.experience.years} yrs`, esc(r.experience.source)],
    ["Closest role", esc(best.role), `skill similarity ${best.similarity.toFixed(2)}`],
    ["Competencies", r.families_detected.length ? `${r.families_detected.length} of 5` : "none",
      r.families_detected.map((f) => esc(r.family_labels[f])).join(", ") || "none of the five detected"],
  ].map(([k, v, s]) => `<div><div class="k">${k}</div><div class="v">${v}</div><div class="r">${s}</div></div>`).join("");

  const known = new Set(r.skills_known_to_roles);
  document.getElementById("resume-skills").innerHTML = r.skills.length
    ? r.skills.map((s) => `<li class="${known.has(s) ? "known" : ""}">${esc(s)}</li>`).join("")
    : "<li>No known skills found. Check that the resume lists skills as words, not only as logos or images.</li>";
  document.getElementById("resume-skill-note").textContent =
    `${r.note} Outlined skills are used in the role comparison; the rest still feed the salary model.`;

  const rows = [...r.ranking].reverse(); // Plotly draws horizontal bars bottom-up
  const groups = [["data", "Data roles", t.s1], ["adjacent", "Adjacent roles", t.s2]];
  plot("resume-roles", groups.map(([g, name, color]) => {
    const sub = rows.filter((x) => x.group === g);
    return {
      type: "bar", orientation: "h", name, y: sub.map((x) => x.role), x: sub.map((x) => x.similarity),
      marker: { color }, customdata: sub.map((x) => [x.matched_top_skills.join(", ") || "none", x.band_median]),
      hovertemplate: "%{y}<br>similarity %{x:.2f}<br>matched top skills: %{customdata[0]}<br>typical band %{customdata[1]} L<extra></extra>",
    };
  }), {
    showlegend: true, barmode: "overlay",
    xaxis: { title: { text: "skill similarity (0 none, 1 identical)" }, rangemode: "tozero" },
    yaxis: { categoryorder: "array", categoryarray: rows.map((x) => x.role), gridcolor: "rgba(0,0,0,0)" },
  });

  const top = r.ranking.filter((x) => x.group === "data").slice(0, 3);
  document.getElementById("resume-top").innerHTML = table(
    ["Role", "Similarity", "You already have", "Worth adding", "Typical band"],
    top.map((x) => [esc(x.role), x.similarity.toFixed(2), esc(x.matched_top_skills.join(", ") || "–"),
      esc(x.skills_to_add.join(", ") || "–"), `${esc(x.band_median)} L`]), { numeric: [1] });
  drawBand();
}

function drawBand() {
  if (!band) return;
  const t = tokens();
  document.getElementById("resume-band").textContent = `${band.predicted_band} L`;
  plot("resume-band-chart", [{
    type: "bar", x: band.probabilities.map((p) => p.band), y: band.probabilities.map((p) => p.probability),
    marker: { color: t.s1 }, hovertemplate: "%{x} lakhs: %{y:.1%}<extra></extra>",
  }], { yaxis: { tickformat: ".0%", rangemode: "tozero" },
        xaxis: { title: { text: "salary band (lakhs per year)" }, gridcolor: "rgba(0,0,0,0)" } });
  document.getElementById("resume-years-note").textContent =
    "Change the years or the role to re-estimate. The experience range sent to the model is your years to your years + 3.";
}
