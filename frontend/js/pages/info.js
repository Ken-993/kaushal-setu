// info.js - the text-only tabs: Findings and Data & cleaning.
import { api } from "../api.js";
import { esc, table } from "../charts.js";

export async function initFindings() {
  const o = await api.overview();
  document.getElementById("findings").innerHTML = o.insights.map((i) => `
    <li>
      <p class="area">${esc(i.area)}</p>
      <h3>${esc(i.title)}</h3>
      <p>${esc(i.text)}</p>
      <p class="ev">Source: ${esc(i.evidence)}</p>
    </li>`).join("");
}

export async function initData() {
  const [o, p] = await Promise.all([api.overview(), api.options()]);
  document.getElementById("audit").innerHTML = table(
    ["Dataset", "Rows", "Columns", "Missing cells", "Duplicate rows", "Repeated IDs"],
    o.audit.map((a) => [esc(a.dataset), a.rows.toLocaleString(), a.cols, a.missing_cells.toLocaleString(), a.row_duplicates, a.dup_ids]),
    { numeric: [1, 2, 3, 4, 5] });
  document.getElementById("decisions").innerHTML = table(
    ["Dataset", "Decision", "Detail"], o.decisions.map((d) => [esc(d.dataset), esc(d.decision), esc(d.detail)]));
  const c = o.coverage;
  const unmapped = Object.entries(c.unmapped_top_titles).map(([k, v]) => `${esc(k)} (${v})`).join("; ");
  document.getElementById("coverage").innerHTML =
    `<p>${c.mapped.toLocaleString()} of ${c.analytics_postings.toLocaleString()} analytics postings were matched to one of ${o.n_roles} roles
      (a role needs at least ${c.min_postings} postings). Titles are matched by ordered keyword rules in
      <code>pipeline/profiles.py</code>; the first rule that matches wins.</p>
     <p class="hint">Most common unmatched titles: ${unmapped}</p>
     ${table(["Role", "Group"], p.roles.map((r, i) => [esc(r), p.groups[i] === "data" ? "Data role" : "Adjacent role"]))}`;
}
