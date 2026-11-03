// api.js - the only file that talks to the backend.
// Every other module calls these functions instead of using fetch() directly.

// When the page is served by FastAPI (http://127.0.0.1:8000) the API is on the same origin, so
// the base is "". When it is opened from VS Code Live Server (port 5500) we point at port 8000.
export const API_BASE = location.port === "5500" ? "http://127.0.0.1:8000" : "";

const cache = new Map();

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(API_BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    throw new Error("Cannot reach the server. If the site was asleep it takes about a minute to wake up: " +
      "wait, then reload the page. Running it yourself? Check that the container is running.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* body was not JSON */ }
    if (Array.isArray(detail)) detail = detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join("; ");
    throw new Error(`${path} failed (${res.status}): ${detail}`);
  }
  return res.json();
}

// GET requests are cached: the artifacts do not change while the server runs.
export function get(path) {
  if (!cache.has(path)) cache.set(path, request(path).catch((e) => { cache.delete(path); throw e; }));
  return cache.get(path);
}

export function post(path, body) {
  return request(path, { method: "POST", body: JSON.stringify(body) });
}

export const api = {
  options: () => get("/api/options"),
  overview: () => get("/api/overview"),
  stats: () => get("/api/stats"),
  models: () => get("/api/models"),
  similarity: (view) => get(`/api/similarity?view=${encodeURIComponent(view)}`),
  profile: (role) => get(`/api/profiles/${encodeURIComponent(role)}`),
  compare: (a, b) => get(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  match: (scores) => post("/api/match", scores),
  success: (scores) => post("/api/predict/success", scores),
  band: (posting) => post("/api/predict/salary-band", posting),
  // file upload: sent as multipart form data, so no JSON Content-Type header here
  resume: async (file, city) => {
    const form = new FormData();
    form.append("file", file);
    form.append("city", city);
    let res;
    try {
      res = await fetch(API_BASE + "/api/resume", { method: "POST", body: form });
    } catch {
      throw new Error("Cannot reach the server. Wait a moment and try again.");
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Upload failed (${res.status})`);
    return body;
  },
};
