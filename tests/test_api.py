"""Smoke tests for the API. Run from the project root after `python run_all.py`:

    pytest -q

TestClient sends requests to the app in memory, so no server needs to be running.
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
JUNIOR = {"big_data_skills": 3.2, "maths_stats_skills": 4.1, "coding_skills": 3.9,
          "ai_and_ml_skills": 3.5, "dashboard_and_storytelling_skills": 4.2}


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_frontend_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()


def test_read_endpoints():
    for url in ["/api/overview", "/api/options", "/api/stats", "/api/models", "/api/profiles"]:
        assert client.get(url).status_code == 200, url


def test_similarity_views_are_square_and_symmetric():
    roles = client.get("/api/options").json()["roles"]
    for view in ["skills", "competency", "salary", "career", "blended"]:
        d = client.get("/api/similarity", params={"view": view}).json()
        m = d["matrix"]
        assert len(m) == len(roles) and all(len(r) == len(roles) for r in m)
        assert all(abs(m[i][j] - m[j][i]) < 1e-9 for i in range(len(m)) for j in range(len(m)))
        assert all(m[i][i] == 0 for i in range(len(m)))
        assert len(d["xy"]) == len(roles)


def test_unknown_view_is_404():
    assert client.get("/api/similarity", params={"view": "nope"}).status_code == 404


def test_profile_with_slash_in_name():
    r = client.get("/api/profiles/ML%20%2F%20AI%20Engineer")
    assert r.status_code == 200 and r.json()["role"] == "ML / AI Engineer"


def test_compare():
    d = client.get("/api/compare", params={"a": "Data Scientist", "b": "Data Analyst"}).json()
    assert set(d["distances"]) == {"skills", "competency", "salary", "career", "blended"}
    assert d["test"]["a"] == "Data Scientist"
    assert 0 <= d["jaccard_top20"] <= 1


def test_predict_hike_and_monotonic_in_skills():
    low = client.post("/api/predict/hike", json={k: 2.5 for k in JUNIOR}).json()["probability"]
    high = client.post("/api/predict/hike", json={k: 4.8 for k in JUNIOR}).json()["probability"]
    assert 0 <= low < high <= 1


def test_predict_rejects_out_of_range():
    assert client.post("/api/predict/hike", json={**JUNIOR, "coding_skills": 9}).status_code == 422


def test_predict_success():
    d = client.post("/api/predict/success", json={"neuroticism": 36, "extraversion": 50,
                                                  "openness_to_experience": 55, "agreeableness": 45,
                                                  "conscientiousness": 58}).json()
    assert 0 <= d["probability"] <= 1 and len(d["contributions"]) == 5


def test_predict_band_more_experience_pays_more():
    base = {"skills": ["python", "sql"], "job_title": "data scientist", "city": "bengaluru"}
    junior = client.post("/api/predict/salary-band", json={**base, "exp_min": 0, "exp_max": 2}).json()
    senior = client.post("/api/predict/salary-band", json={**base, "exp_min": 10, "exp_max": 15}).json()
    assert abs(sum(p["probability"] for p in junior["probabilities"]) - 1) < 1e-3
    assert senior["expected_band_index"] > junior["expected_band_index"]


def test_match():
    d = client.post("/api/match", json=JUNIOR).json()
    sims = [r["similarity"] for r in d["ranking"]]
    assert sims == sorted(sims, reverse=True)


# ------------------------------------------------------------------ resume upload
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def _upload(name, content, city="pune"):
    return client.post("/api/resume", files={"file": (name, content)}, data={"city": city})


def test_resume_all_formats_agree():
    results = {}
    for ext in ["txt", "docx", "pdf"]:
        r = _upload(f"sample_resume.{ext}", (SAMPLES / f"sample_resume.{ext}").read_bytes())
        assert r.status_code == 200, (ext, r.text)
        results[ext] = r.json()
    for d in results.values():
        assert {"python", "sql", "tableau", "power bi", "statistics"} <= set(d["skills"])
        assert d["experience"]["years"] == 3
        assert d["best_data_role"] in {"Data Analyst", "BI & Reporting Analyst"}
        assert abs(sum(p["probability"] for p in d["salary_band"]["probabilities"]) - 1) < 1e-3
    assert results["txt"]["skills"] == results["docx"]["skills"] == results["pdf"]["skills"]


def test_resume_rejects_bad_files():
    assert _upload("cv.doc", b"old word file").status_code == 422
    assert _upload("cv.txt", b"too short").status_code == 422
    assert _upload("cv.pdf", b"not really a pdf").status_code == 422


# ------------------------------------------------------------------ job-role fit
def test_fit_by_hand_and_verdicts():
    d = client.post("/api/fit", json={"skills": ["python", "sql", "excel", "data analysis", "tableau"],
                                      "years": 4, "city": "pune"}).json()
    roles = d["roles"]
    assert len(roles) == 19 and all(0 <= r["match"] <= 1 for r in roles)
    assert {r["verdict"] for r in roles} <= {"ready", "almost", "stretch"}
    levels = [r["level"] for r in roles]
    assert levels == sorted(levels, reverse=True)
    da = next(r for r in roles if r["role"] == "Data Analyst")
    assert "sql" in da["have"] and da["verdict"] in {"ready", "almost"}


def test_more_skills_never_lower_the_match():
    base = {"skills": ["python"], "years": 3}
    more = {"skills": ["python", "machine learning", "deep learning", "nlp"], "years": 3}
    m1 = {r["role"]: r["match"] for r in client.post("/api/fit", json=base).json()["roles"]}
    m2 = {r["role"]: r["match"] for r in client.post("/api/fit", json=more).json()["roles"]}
    assert all(m2[k] >= m1[k] for k in m1)


def test_fit_sample_and_picker():
    d = client.get("/api/fit/sample").json()
    assert d["counts"]["ready"] >= 1 and d["experience"]["years"] == 3
    groups = client.get("/api/skill-picker").json()
    assert len(groups) >= 5 and all(g["skills"] for g in groups)
    assert client.post("/api/fit", json={"skills": [], "years": 1}).status_code == 422
