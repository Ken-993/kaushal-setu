// fit.js - "Check my fit": upload a resume (or pick skills) and see your fit for every role.
import { api } from "../api.js";
import { cityName, esc, fmtBand } from "../charts.js";

let ctx;                       // { openRole(role) } from app.js
let state = null;              // last result: { roles, skills, years, city, ... }
let filter = "all";
const picked = new Set();

const $ = (id) => document.getElementById(id);

export async function init(appCtx) {
  ctx = appCtx;
  const [opts, picker] = await Promise.all([api.options(), api.skillPicker()]);
  const cityOpts = opts.cities.map((c) => `<option value="${esc(c)}" ${c === "bengaluru" ? "selected" : ""}>${esc(cityName(c))}</option>`).join("");
  $("fit-city").innerHTML = cityOpts;
  $("pick-city").innerHTML = cityOpts;
  $("skill-list").innerHTML = opts.skills.map((s) => `<option value="${esc(s)}">`).join("");

  // tabs: upload vs pick
  const tabs = [["tab-upload", "panel-upload"], ["tab-pick", "panel-pick"]];
  tabs.forEach(([t, p]) => $(t).addEventListener("click", () => {
    tabs.forEach(([t2, p2]) => { $(t2).setAttribute("aria-selected", t2 === t); $(p2).hidden = p2 !== p; });
    setError("");
  }));

  // skill picker chips
  $("picker").innerHTML = picker.map((g) => `
    <div><h4>${esc(g.group)}</h4>${g.skills.map((s) =>
      `<button type="button" class="toggle-chip" aria-pressed="false" data-skill="${esc(s)}">${esc(s)}</button>`).join("")}</div>`).join("");
  $("picker").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-skill]");
    if (!b) return;
    const on = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", on);
    on ? picked.add(b.dataset.skill) : picked.delete(b.dataset.skill);
  });
  $("pick-extra").addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    addPicked(e.target.value);
    e.target.value = "";
  });

  // drag & drop upload
  const input = $("resume-file"), drop = $("drop");
  input.addEventListener("change", () => { $("drop-title").textContent = input.files[0]?.name ?? "Drop your resume here or browse"; });
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; $("drop-title").textContent = input.files[0].name; }
  });

  $("panel-upload").addEventListener("submit", (e) => { e.preventDefault(); fromResume(); });
  $("fit-sample").addEventListener("click", () => run(() => api.fitSample($("fit-city").value), $("fit-go"), "sample resume"));
  $("panel-pick").addEventListener("submit", (e) => { e.preventDefault(); fromPicker(); });

  // results controls
  $("add-skill").addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || !state) return;
    e.preventDefault();
    const v = e.target.value.trim().toLowerCase();
    if (v && !state.skills.includes(v)) { state.skills.push(v); renderSkills(); }
    e.target.value = "";
  });
  $("my-skills").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-rm]");
    if (!b || !state) return;
    state.skills = state.skills.filter((s) => s !== b.dataset.rm);
    renderSkills();
  });
  $("recheck").addEventListener("click", () => {
    if (!state || !state.skills.length) { setError("Add at least one skill first."); return; }
    const years = Number($("my-years").value) || 0;
    run(() => api.fit(state.skills, years, state.city), $("recheck"), state.source);
  });
  $("role-filter").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-f]");
    if (!b) return;
    filter = b.dataset.f;
    $("role-filter").querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", x === b));
    renderAll();
  });
  $("top-matches").addEventListener("click", openRoleFrom);
  $("all-roles").addEventListener("click", openRoleFrom);
}

function openRoleFrom(e) {
  const b = e.target.closest("[data-role]");
  if (b) ctx.openRole(b.dataset.role);
}


function addPicked(raw) {
  const v = raw.trim().toLowerCase();
  if (!v) return;
  picked.add(v);
  const existing = $("picker").querySelector(`button[data-skill="${CSS.escape(v)}"]`);
  if (existing) existing.setAttribute("aria-pressed", "true");
  else {
    let extra = $("picker").querySelector("[data-extra]");
    if (!extra) {
      extra = document.createElement("div");
      extra.dataset.extra = "1";
      extra.innerHTML = "<h4>Added by you</h4>";
      $("picker").prepend(extra);
    }
    extra.insertAdjacentHTML("beforeend",
      `<button type="button" class="toggle-chip" aria-pressed="true" data-skill="${esc(v)}">${esc(v)}</button>`);
  }
}

function setError(msg) {
  $("fit-error").textContent = msg || "";
  $("fit-error").hidden = !msg;
}

function fromResume() {
  const file = $("resume-file").files[0];
  if (!file) { setError("Choose your resume file first, or try the sample resume."); return; }
  run(() => api.resume(file, $("fit-city").value), $("fit-go"), file.name);
}

function fromPicker() {
  addPicked($("pick-extra").value);
  $("pick-extra").value = "";
  if (!picked.size) { setError("Tap at least one skill you have."); return; }
  run(() => api.fit([...picked], Number($("pick-years").value) || 0, $("pick-city").value), $("pick-go"), "skills you picked");
}

async function run(call, btn, source) {
  setError("");
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Checking…";
  try {
    const res = await call();
    state = { ...res, skills: [...res.skills], source };
    render();
    $("results").hidden = false;
    $("how").hidden = true;
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    setError(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

export function redraw() { if (state) render(); }

function render() {
  const s = state;
  const yrs = s.experience?.years ?? s.years;
  const src = s.experience?.source;
  $("profile-sub").textContent =
    `From your ${s.source}: ${s.skills.length} skills and about ${yrs} year${yrs === 1 ? "" : "s"} of experience` +
    (src && !/stated/.test(src) ? ` (${src})` : "") + ". Remove anything wrong, add what's missing, then update.";
  $("my-years").value = yrs;
  const c = s.counts;
  $("tally").innerHTML = `
    <span class="badge ready">${c.ready} ready to apply</span>
    <span class="badge almost">${c.almost} almost there</span>
    <span class="badge stretch">${c.stretch} stretch</span>`;
  renderSkills();
  renderTop();
  renderAll();
  $("method-note").textContent =
    "Match % = how much of the 10 skills employers ask for most in that role you have, weighted by how often each is asked for. " +
    "Ready to apply: 50%+. Almost there: 25%+. One level lower if you're more than 2 years short of the experience the role usually asks for.";
}

function renderSkills() {
  $("my-skills").innerHTML = state.skills.length
    ? state.skills.map((k) => `<li class="chip">${esc(k)}<button type="button" data-rm="${esc(k)}" aria-label="Remove ${esc(k)}">×</button></li>`).join("")
    : `<li class="muted">No skills found. Add some below.</li>`;
}

function ring(pct, verdict) {
  const r = 34, c = 2 * Math.PI * r, off = c * (1 - pct);
  return `<svg class="ring" viewBox="0 0 86 86" aria-hidden="true">
    <circle cx="43" cy="43" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="9"/>
    <circle cx="43" cy="43" r="${r}" fill="none" stroke="var(--${verdict})" stroke-width="9" stroke-linecap="round"
      stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" transform="rotate(-90 43 43)"/>
    <text x="43" y="49" text-anchor="middle" font-size="19">${Math.round(pct * 100)}%</text></svg>`;
}

function expLine(e) {
  const need = e.usual_min_years, you = e.your_years;
  const cls = { meets: "exp-ok", close: "exp-close", short: "exp-short" }[e.status];
  const word = { meets: "✓ meets it", close: "◐ close", short: `✕ ${Math.max(0, need - you)} yr short` }[e.status];
  return `<span class="${cls}">${word}</span>`;
}

function renderTop() {
  $("top-matches").innerHTML = state.roles.slice(0, 3).map((r) => `
    <article class="match-card">
      <div class="match-top">
        <div><span class="badge ${r.verdict}">${r.verdict_label}</span><h3>${esc(r.role)}</h3></div>
        ${ring(r.match, r.verdict)}
      </div>
      <dl class="facts">
        <div><dt>Key skills you have</dt><dd>${r.have.length} of ${r.key_skills.length}</dd></div>
        <div><dt>Experience (usually ${r.experience.usual_min_years}+ yrs)</dt><dd>${expLine(r.experience)}</dd></div>
        <div><dt>Typical pay</dt><dd>${fmtBand(r.typical_band)}</dd></div>
        <div><dt>Your likely pay</dt><dd>${fmtBand(r.your_band)}</dd></div>
      </dl>
      ${r.have.length ? `<div><h4>You already have</h4><ul class="chips">${r.have.map((k) => `<li class="chip have">${esc(k)}</li>`).join("")}</ul></div>` : ""}
      ${r.missing.length ? `<div><h4>Learn next</h4><ul class="chips">${r.missing.slice(0, 4).map((k) => `<li class="chip miss">${esc(k)}</li>`).join("")}</ul></div>` : ""}
      <button type="button" class="btn secondary" data-role="${esc(r.role)}">Explore this role</button>
    </article>`).join("");
}

function renderAll() {
  const rows = state.roles.filter((r) => filter === "all" || r.group === "data");
  $("all-roles").innerHTML = rows.map((r) => `
    <button type="button" class="role-row" data-role="${esc(r.role)}">
      <span class="name">${esc(r.role)}<small>${r.have.length} of ${r.key_skills.length} key skills${r.missing.length ? `, missing ${esc(r.missing.slice(0, 2).join(", "))}` : ""}</small></span>
      <span class="row-bar"><span class="bar ${r.verdict}"><span style="width:${Math.max(2, r.match * 100).toFixed(0)}%"></span></span><span class="pct">${Math.round(r.match * 100)}%</span></span>
      <span class="badge ${r.verdict}">${r.verdict_label}</span>
      <span class="pay">${fmtBand(r.typical_band)}</span>
    </button>`).join("");
}
