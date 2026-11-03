"""The 'brain' of the backend: loads the artifacts made by the pipeline and answers questions.

main.py only handles web requests; every calculation lives here so it can be tested
without a web server (see tests/test_api.py).

Nothing is trained here. The pipeline (python run_all.py) must have been run first; this
module only READS artifacts/*.json and artifacts/*.joblib.
"""
import json
import re
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from config import ART, CLEAN, JDS_FEATURES, SDS_FEATURES, TAXONOMY
from pipeline.cleaning import _match_family

FAMILY_COLS = ["has_big_data", "has_maths_stats", "has_coding", "has_ai_ml", "has_dashboards"]


class ArtifactsMissing(RuntimeError):
    pass


def _json(name: str):
    path = ART / name
    if not path.exists():
        raise ArtifactsMissing(f"{path} not found - run `python run_all.py` first.")
    return json.loads(path.read_text())


@lru_cache(maxsize=None)  # load each file once, then keep it in memory
def store() -> dict:
    s = {n: _json(f"{n}.json") for n in ["stats", "models", "profiles", "insights"]}
    s["cleaning"] = json.loads((CLEAN / "cleaning_report.json").read_text())
    for name in ["jds", "sds", "band"]:
        path = ART / f"{name}_model.joblib"
        if not path.exists():
            raise ArtifactsMissing(f"{path} not found - run `python run_all.py` first.")
        s[f"{name}_model"] = joblib.load(path)
    p = s["profiles"]
    s["role_index"] = {r: i for i, r in enumerate(p["roles"])}
    return s


# ------------------------------------------------------------------ read-only views
def overview() -> dict:
    s = store()
    p = s["profiles"]
    return {"audit": s["cleaning"]["audit"], "decisions": s["cleaning"]["decisions"],
            "insights": s["insights"], "coverage": p["coverage"], "n_roles": len(p["roles"])}


def options() -> dict:
    """Everything a form on the website needs: allowed skills, cities, roles, input ranges."""
    s = store()
    m, p = s["models"], s["profiles"]
    return {"roles": p["roles"], "groups": p["groups"], "bands": p["bands"],
            "skills": m["band"]["skill_vocabulary"], "cities": m["band"]["cities"],
            "families": p["families"], "family_labels": p["family_labels"],
            "jds": {k: m["jds"][k] for k in ["features", "feature_means", "feature_min", "feature_max"]},
            "sds": {k: m["sds"][k] for k in ["features", "feature_means", "feature_min", "feature_max"]},
            "views": {k: {"label": v["label"], "metric": v["metric"], "range": v["range"]}
                      for k, v in p["views"].items()}}


def models_summary() -> dict:
    m = json.loads(json.dumps(store()["models"]))  # deep copy so we can trim it
    m["band"].pop("skill_vocabulary", None)
    return m


def profiles_list() -> list[dict]:
    keep = ["role", "group", "n", "pct_of_postings", "senior_share", "exp_min_mean", "band_mean", "band_median",
            "family_prevalence", "band_distribution"]
    out = []
    for prof in store()["profiles"]["profiles"]:
        row = {k: prof[k] for k in keep}
        row["avg_salary_lakhs"] = prof.get("dsjobs", {}).get("avg_salary_lakhs")
        out.append(row)
    return out


def _check_role(role: str) -> int:
    idx = store()["role_index"]
    if role not in idx:
        raise KeyError(f"unknown role '{role}'. Valid roles: {list(idx)}")
    return idx[role]


def profile(role: str) -> dict:
    i = _check_role(role)
    p = store()["profiles"]
    nearest = {}
    for key, v in p["views"].items():
        row = v["matrix"][i]
        order = [j for j in np.argsort(row) if j != i][:5]
        nearest[key] = [{"role": p["roles"][j], "distance": row[j]} for j in order]
    return {**p["profiles"][i], "nearest": nearest}


def similarity(view: str) -> dict:
    p = store()["profiles"]
    if view not in p["views"]:
        raise KeyError(f"unknown view '{view}'. Valid views: {list(p['views'])}")
    v = p["views"][view]
    return {"view": view, "roles": p["roles"], "groups": p["groups"],
            "n": [x["n"] for x in p["profiles"]], "band_mean": [x["band_mean"] for x in p["profiles"]],
            **v}


def compare(a: str, b: str) -> dict:
    """Side-by-side comparison of two job profiles on every distance view + the pairwise tests."""
    ia, ib = _check_role(a), _check_role(b)
    p = store()["profiles"]
    n = len(p["roles"])
    distances = {}
    for key, v in p["views"].items():
        row = np.array(v["matrix"][ia])
        rank = int((np.argsort(np.argsort(row)))[ib])  # 1 = b is a's closest role
        all_d = np.array(v["matrix"])[np.triu_indices(n, 1)]
        distances[key] = {"label": v["label"], "metric": v["metric"], "distance": float(row[ib]),
                          "rank_from_a": rank, "of": n - 1,
                          "percentile_of_all_pairs": round(float((all_d < row[ib]).mean() * 100), 1)}

    test = next((t for t in p["pairs"] if {t["a"], t["b"]} == {a, b}), None)
    if test is not None and test["a"] != a:  # stored as (b, a): flip the signed differences
        test = {**test, "a": a, "b": b, "band_diff": -test["band_diff"], "exp_diff": -test["exp_diff"]}

    vocab = p["skill_vocab"]
    Pa, Pb = np.array(p["skill_prevalence"][ia]), np.array(p["skill_prevalence"][ib])
    top_a, top_b = set(np.argsort(-Pa)[:20]), set(np.argsort(-Pb)[:20])
    union = sorted(set(np.argsort(-Pa)[:12]) | set(np.argsort(-Pb)[:12]), key=lambda j: -(Pa[j] + Pb[j]))
    diff = np.argsort(-np.abs(Pa - Pb))[:12]
    return {"a": p["profiles"][ia], "b": p["profiles"][ib], "distances": distances, "test": test,
            "skills_side_by_side": [{"skill": vocab[j], "a": float(Pa[j]), "b": float(Pb[j])} for j in union],
            "most_different_skills": [{"skill": vocab[j], "a": float(Pa[j]), "b": float(Pb[j]),
                                       "diff": float(Pa[j] - Pb[j])} for j in diff],
            "shared_top20": [vocab[j] for j in sorted(top_a & top_b, key=lambda j: -(Pa[j] + Pb[j]))],
            "jaccard_top20": round(len(top_a & top_b) / len(top_a | top_b), 3),
            "families": p["families"], "family_labels": p["family_labels"], "bands": p["bands"]}


# -------------------------------------------------------------------- predictions
def _binary_predict(key: str, values: dict, features: list[str]) -> dict:
    s = store()
    bundle, info = s[f"{key}_model"], s["models"][key]
    x = np.array([[values[f] for f in features]], dtype=float)
    prob = float(bundle["model"].predict_proba(x)[0, 1])

    # explanation: logistic coefficients x standardised distance from the average person
    lr = bundle["explainer"]
    scaler, clf = lr.named_steps["scale"], lr.named_steps["clf"]
    z = (x[0] - scaler.mean_) / scaler.scale_
    contrib = clf.coef_[0] * z
    outside = [f for f in features if not info["feature_min"][f] <= values[f] <= info["feature_max"][f]]
    return {"probability": round(prob, 4), "label": "high" if prob >= 0.5 else "low", "model": bundle["chosen"],
            "baseline_rate": info["positive_rate"],
            "contributions": [{"feature": f, "value": values[f], "average": info["feature_means"][f],
                               "z": round(float(zi), 2), "log_odds": round(float(c), 3)}
                              for f, zi, c in zip(features, z, contrib)],
            "explanation_note": ("Contributions come from the logistic model: positive pushes the probability up "
                                 "compared with an average employee, negative pulls it down."
                                 + ("" if bundle["chosen"] == "logistic regression" else
                                    f" The probability itself comes from the {bundle['chosen']}, so the bars "
                                    "explain the direction, not the exact number.")),
            "outside_training_range": outside}


def predict_hike(values: dict) -> dict:
    return _binary_predict("jds", values, JDS_FEATURES)


def predict_success(values: dict) -> dict:
    return _binary_predict("sds", values, SDS_FEATURES)


def predict_band(exp_min: float, exp_max: float, skills: list[str], job_title: str, city: str) -> dict:
    s = store()
    bundle = s["band_model"]
    exp_max = max(exp_max, exp_min)
    tokens = [t.strip().lower() for t in skills if t.strip()]
    row = {"exp_min": exp_min, "exp_max": exp_max, "exp_span": exp_max - exp_min,
           "skill_tokens": "|".join(tokens), "job_desig": job_title.lower(),
           "city_primary": city.strip().lower() or "unknown"}
    for col, fam in zip(FAMILY_COLS, ["big_data", "maths_stats", "coding", "ai_ml", "dashboards"]):
        row[col] = int(_match_family(tokens, TAXONOMY[fam]))
    X = pd.DataFrame([row])
    probs = bundle["model"].predict_proba(X)[0]
    bands = bundle["bands"]
    known = set(s["models"]["band"]["skill_vocabulary"])
    return {"probabilities": [{"band": b, "probability": round(float(pr), 4)} for b, pr in zip(bands, probs)],
            "predicted_band": bands[int(np.argmax(probs))],
            "expected_band_index": round(float(np.dot(np.arange(len(bands)), probs)), 3),
            "families_detected": [c.replace("has_", "") for c in FAMILY_COLS if row[c]],
            "unknown_skills": [t for t in tokens if t not in known],
            "note": "Bands are salary ranges in lakhs per year as written in the Analytics Jobs file."}


def match_roles(values: dict) -> dict:
    """Rank the data job profiles by how well a person's skill PATTERN fits each role's demand PATTERN.

    person : z-score of each JDS skill against the company's juniors, then centred on the person's
             own average -> positive = one of your relative strengths, negative = relative weakness
    role   : log-lift of each competency family in the role vs all postings, centred the same way
             -> positive = what this role asks for more than the other competencies
    pattern_match : cosine between the two centred vectors (-1 opposite, 0 unrelated, +1 same shape)
    coverage      : sum(demand x level) / sum(demand), demand = share of the role's postings asking for
                    the family, level = (score - 1) / 4  -> how much of what the role asks for you have
    Only 'data' roles are ranked: adjacent roles (HR, sales, ...) barely ask for any of the five
    competencies, so their pattern would be noise.
    """
    s = store()
    m, p = s["models"]["jds"], s["profiles"]
    fams, f2j = p["families"], p["family_to_jds"]
    z = np.array([(values[f2j[f]] - m["feature_means"][f2j[f]]) / m["feature_sds"][f2j[f]] for f in fams])
    level = np.array([(values[f2j[f]] - 1) / 4 for f in fams])
    person = z - z.mean()
    flat = bool(np.linalg.norm(person) < 0.2)
    rows = []
    for prof in p["profiles"]:
        if prof["group"] != "data":
            continue
        emph = np.array([prof["family_emphasis"][f] for f in fams])
        role = emph - emph.mean()
        demand = np.array([prof["family_prevalence"][f] for f in fams])
        cos = 0.0 if flat else float(person @ role / (np.linalg.norm(person) * np.linalg.norm(role)))
        coverage = float((demand * level).sum() / demand.sum()) if demand.sum() else 0.0
        gaps = [{"family": f, "label": p["family_labels"][f], "role_emphasis": round(float(role[k]), 3),
                 "your_relative": round(float(person[k]), 2)}
                for k, f in enumerate(fams) if role[k] > 0 and person[k] < 0]
        rows.append({"role": prof["role"], "similarity": round(cos, 3), "fit_pct": round((cos + 1) * 50, 1),
                     "coverage_pct": round(100 * coverage, 1), "band_median": prof["band_median"],
                     "band_mean": prof["band_mean"], "demand": {f: round(float(d), 3) for f, d in zip(fams, demand)},
                     "skills_to_build": sorted(gaps, key=lambda g: -g["role_emphasis"])})
    rows.sort(key=lambda r: (-r["coverage_pct"]) if flat else (-r["similarity"], -r["coverage_pct"]))
    return {"your_profile": [{"family": f, "label": p["family_labels"][f], "z": round(float(v), 2),
                              "relative": round(float(r), 2)} for f, v, r in zip(fams, z, person)],
            "flat_profile": flat, "ranking": rows, "hike": predict_hike(values),
            "method": match_roles.__doc__.strip()}


# ------------------------------------------------------------------------ resume
def analyse_resume(filename: str, content: bytes, city: str = "bengaluru") -> dict:
    """Read a resume, find its skills and experience, then rank roles and estimate a salary band.

    role similarity : cosine between the resume's skill vector (1 = skill present) and each role's
                      skill-prevalence vector - the same skill space as the Atlas 'Skill overlap' view
    skills to add   : skills listed by at least 8% of the role's postings that the resume does not mention
    salary band     : the band model, with the detected skills, years of experience, the best-fitting
                      data role as the job title, and the chosen city
    """
    from backend import resume as rp

    text = rp.extract_text(filename, content)
    words = len(text.split())
    if words < 40:
        raise rp.ResumeError("Almost no text could be read from this file. If it is a scanned image, "
                             "export a text-based PDF from Word/Google Docs, or upload the .docx instead.")
    s = store()
    p = s["profiles"]
    vocab = sorted(set(s["models"]["band"]["skill_vocabulary"]) | set(p["skill_vocab"]))
    skills = rp.find_skills(text, vocab)
    years = rp.find_years(text)
    fams = p["families"]
    detected = [f for f in fams if _match_family(skills, TAXONOMY[f])]

    found = set(skills)
    v = np.array([1.0 if t in found else 0.0 for t in p["skill_vocab"]])
    ranking = []
    for i, prof in enumerate(p["profiles"]):
        prev = np.array(p["skill_prevalence"][i])
        denom = np.linalg.norm(v) * np.linalg.norm(prev)
        sim = float(v @ prev / denom) if denom else 0.0
        top = [t["skill"] for t in prof["top_skills"]]
        missing = [p["skill_vocab"][j] for j in np.argsort(-prev)
                   if prev[j] >= 0.08 and p["skill_vocab"][j] not in found
                   and p["skill_vocab"][j] not in rp.IGNORE
                   and not re.search(r"(analyst|scientist|engineer|manager|developer)$", p["skill_vocab"][j])][:6]
        ranking.append({"role": prof["role"], "group": prof["group"], "similarity": round(sim, 3),
                        "matched_top_skills": [t for t in top if t in found],
                        "skills_to_add": missing, "band_median": prof["band_median"]})
    ranking.sort(key=lambda r: -r["similarity"])
    best_data = next(r["role"] for r in ranking if r["group"] == "data")
    band = predict_band(years["years"], years["years"] + 3, skills, best_data, city)
    return {"file": filename, "words": words, "skills": skills,
            "skills_known_to_roles": [t for t in skills if t in set(p["skill_vocab"])],
            "experience": years, "families_detected": detected,
            "family_labels": p["family_labels"], "ranking": ranking, "best_data_role": best_data,
            "salary_band": band, "city": city,
            "note": ("Keyword matching: skills are found only when written the way job postings write them. "
                     "The file was read in memory and not saved."),
            "method": analyse_resume.__doc__.strip()}
