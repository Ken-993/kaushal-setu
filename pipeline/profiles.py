"""Phase 4 - job profiles and the distances between them.

1. Every Analytics posting gets a canonical ROLE from its designation (ordered regex rules,
   first match wins; unmatched postings are left out of the role map, not forced in).
2. Each role becomes a PROFILE: skill prevalence, competency-family prevalence, experience,
   salary-band distribution, top cities, example titles, and (where the title exists in the
   DataScience Jobs file) the advertised salary in lakhs.
3. Roles are compared in five DISTANCE VIEWS:
     skills      - cosine distance between skill-prevalence vectors (which skills are asked for)
     competency  - Euclidean distance between 5-family prevalence vectors
     salary      - Jensen-Shannon distance between salary-band distributions
     career      - Euclidean distance on z-scored (mean experience, mean band)
     blended     - average of the four, each rescaled to 0..1
   Each view gets a 2-D map (classical MDS), a hierarchical clustering (average linkage) and
   a dendrogram that the frontend draws.
4. Pairwise SIGNIFICANCE (Holm-corrected across all role pairs):
     skills  - permutation test on the cosine distance (role labels shuffled 999 times).
               With 153 pairs, Holm needs p < 0.05/153 ~ 3e-4, finer than 1/1000, so the
               p-value used for Holm is the normal tail of the permutation null
               (z = (observed - null mean) / null sd). The raw empirical p is kept too.
     salary  - Mann-Whitney U on band
     experience - Mann-Whitney U on exp_min

Output: artifacts/profiles.json
"""
import json
import re
from collections import Counter

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import jensenshannon, pdist, squareform
from statsmodels.stats.multitest import multipletests

from config import ART, BAND_ORDER, CLEAN, JDS_FEATURES, SEED

FAMILIES = ["big_data", "maths_stats", "coding", "ai_ml", "dashboards"]
FAMILY_LABELS = {"big_data": "Big data", "maths_stats": "Maths & stats", "coding": "Coding",
                 "ai_ml": "AI & ML", "dashboards": "Dashboards & storytelling"}
FAMILY_TO_JDS = dict(zip(FAMILIES, JDS_FEATURES))
MIN_POSTINGS = 40
N_PERM = 999

# (role, group, regex) - ORDER MATTERS: the first matching rule wins.
ROLE_RULES = [
    ("ML / AI Engineer", "data", r"machine learning|\bml\b|deep learning|\bai\b|artificial intel|\bnlp\b|computer vision"),
    ("Data Scientist", "data", r"data scien"),
    ("Data Engineer", "data", r"data engineer|big data|hadoop|spark|\betl\b|data warehous"),
    ("Data / Solution Architect", "data", r"architect"),
    ("BI & Reporting Analyst", "data", r"business intelligence|\bbi\b|power ?bi|tableau|qlik|\bmis\b|reporting|dashboard"),
    ("Data Analyst", "data", r"data analyst|analytics analyst|data analytics|analyst.{0,3}analytics"),
    ("Business Analyst", "data", r"business analy"),
    ("Risk & Quant Analyst", "data", r"statistic|quant|actuar|\brisk\b|credit|fraud"),
    ("Analytics Manager / Lead", "data", r"analytics manager|manager.{0,20}analytics|head.{0,20}analytics|analytics lead|lead.{0,20}analytics|vice president.{0,20}analytics"),
    ("Analytics Generalist", "data", r"analytic|^\s*analyst\s*$"),
    ("Research Analyst", "adjacent", r"research analyst|market research"),
    ("Product Manager", "adjacent", r"product manager|product owner"),
    ("Finance & Accounting", "adjacent", r"financial analyst|financ|account|audit|\btax\b"),
    ("Software Engineer", "adjacent", r"software engineer|developer|\bsde\b|programmer|full ?stack|\bjava\b|\.net"),
    ("QA / Test Engineer", "adjacent", r"\btest|\bqa\b|quality"),
    ("SAP Consultant", "adjacent", r"\bsap\b"),
    ("Digital Marketing / SEO", "adjacent", r"digital marketing|\bseo\b|\bsem\b|social media|marketing"),
    ("Sales & Business Dev.", "adjacent", r"\bsales\b|business development"),
    ("HR & Recruitment", "adjacent", r"\bhr\b|recruit|talent|human resource"),
]
_COMPILED = [(n, g, re.compile(p, re.I)) for n, g, p in ROLE_RULES]
SENIOR = re.compile(r"\bsenior\b|\bsr\b|\blead\b|\bprincipal\b|\bhead\b|\bchief\b|\bvp\b|director", re.I)

# Roles that also appear as job titles in DataScience_Jobs.csv (advertised salary in lakhs)
DSJOBS_TITLES = {
    "ML / AI Engineer": ["Machine Learning Engineer"],
    "Data Scientist": ["Data Scientist", "Senior Data Scientist"],
    "Data Engineer": ["Data Engineer", "Senior Data Engineer"],
    "Data / Solution Architect": ["Data Architect"],
    "Data Analyst": ["Data Analyst", "Senior Data Analyst"],
    "Business Analyst": ["Business Analyst", "Senior Business Analyst"],
}


def assign_role(designation) -> str | None:
    d = str(designation)
    for name, _, rx in _COMPILED:
        if rx.search(d):
            return name
    return None


# ------------------------------------------------------------------ helpers
def _skill_matrix(token_lists: list[list[str]], vocab: list[str]) -> np.ndarray:
    idx = {s: i for i, s in enumerate(vocab)}
    M = np.zeros((len(token_lists), len(vocab)), dtype=np.float32)
    for r, toks in enumerate(token_lists):
        for t in set(toks):
            j = idx.get(t)
            if j is not None:
                M[r, j] = 1.0
    return M


def _cos_dist(u, v) -> float:
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    return float(1 - (u @ v) / (nu * nv)) if nu and nv else 1.0


def classical_mds(D: np.ndarray, k: int = 2) -> np.ndarray:
    """Torgerson (classical) MDS: place points in 2-D so straight-line gaps ~ the given distances.
    Deterministic and library-version independent (B = -1/2 * J D^2 J, keep the top-k eigenvectors)."""
    n = len(D)
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ (D ** 2) @ J
    vals, vecs = np.linalg.eigh(B)
    idx = np.argsort(vals)[::-1][:k]
    xy = vecs[:, idx] * np.sqrt(np.clip(vals[idx], 0, None))
    for c in range(k):  # fix the sign so the map does not flip between runs
        if xy[np.argmax(np.abs(xy[:, c])), c] < 0:
            xy[:, c] *= -1
    return xy


def _view(D: np.ndarray, roles: list[str], k: int = 5) -> dict:
    """2-D MDS map + hierarchical clustering + dendrogram coordinates for one distance matrix."""
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0)
    xy = classical_mds(D)
    Z = linkage(squareform(D, checks=False), method="average")
    clusters = fcluster(Z, t=k, criterion="maxclust")
    dn = dendrogram(Z, labels=roles, no_plot=True)
    # normalised stress-1: < 0.1 good, < 0.2 fair
    d_fit = pdist(xy)
    d_true = squareform(D, checks=False)
    stress1 = float(np.sqrt(((d_true - d_fit) ** 2).sum() / (d_true ** 2).sum()))
    return {"matrix": np.round(D, 4).tolist(), "xy": np.round(xy, 4).tolist(),
            "clusters": clusters.astype(int).tolist(), "order": dn["ivl"],
            "dendrogram": {"icoord": dn["icoord"], "dcoord": np.round(dn["dcoord"], 4).tolist(), "ivl": dn["ivl"]},
            "stress1": round(stress1, 3)}


def _perm_skill_test(Xa: np.ndarray, Xb: np.ndarray, rng) -> tuple[float, float, float, float]:
    """Permutation p-value for H0: both roles draw skills from the same distribution."""
    obs = _cos_dist(Xa.mean(0), Xb.mean(0))
    X = np.vstack([Xa, Xb])
    na, n = len(Xa), len(Xa) + len(Xb)
    L = np.zeros((N_PERM, n), dtype=np.float32)
    for b in range(N_PERM):
        L[b, rng.permutation(n)[:na]] = 1.0
    sum_a = L @ X
    mean_a = sum_a / na
    mean_b = (X.sum(0) - sum_a) / (n - na)
    num = (mean_a * mean_b).sum(1)
    den = np.linalg.norm(mean_a, axis=1) * np.linalg.norm(mean_b, axis=1)
    null = 1 - num / np.where(den == 0, 1, den)
    p_emp = float((1 + (null >= obs - 1e-12).sum()) / (1 + N_PERM))
    z = float((obs - null.mean()) / (null.std(ddof=1) + 1e-12))
    return obs, p_emp, z, float(stats.norm.sf(z))


# ------------------------------------------------------------------- driver
def run(frames: dict | None = None) -> dict:
    print("== Phase 4: job profiles & similarity ==")
    if frames is None:
        frames = {"Analytics": pd.read_csv(CLEAN / "Analytics.csv"), "DSJobs": pd.read_csv(CLEAN / "DSJobs.csv")}
    a = frames["Analytics"].copy()
    a = a[~a["non_analytics"].astype(bool)].reset_index(drop=True)
    if not a["skill_tokens"].map(type).eq(list).any():
        a["skill_tokens"] = a["skill_tokens"].fillna("").astype(str).apply(lambda s: [t for t in s.split("|") if t])
    for f in FAMILIES:
        a[f"has_{f}"] = a[f"has_{f}"].astype(bool)

    a["role"] = a["job_desig"].apply(assign_role)
    a["senior"] = a["job_desig"].fillna("").str.contains(SENIOR)
    counts = a["role"].value_counts()
    roles = [n for n, _, _ in ROLE_RULES if counts.get(n, 0) >= MIN_POSTINGS]
    groups = {n: g for n, g, _ in ROLE_RULES}
    r = a[a.role.isin(roles)].reset_index(drop=True)
    print(f"  {len(r)}/{len(a)} postings mapped to {len(roles)} roles (>= {MIN_POSTINGS} postings each)")

    # vocabulary = skills seen in >= 25 role-tagged postings
    tok_count = Counter(t for toks in r.skill_tokens for t in set(toks))
    vocab = sorted([s for s, c in tok_count.items() if c >= 25])
    X = _skill_matrix(r.skill_tokens.tolist(), vocab)
    overall_prev = X.mean(0)
    overall_fam = np.array([a[f"has_{f}"].mean() for f in FAMILIES])
    print(f"  skill vocabulary: {len(vocab)} skills")

    # ---------------- per-role profile
    d = frames["DSJobs"]
    profiles, skill_vecs, fam_vecs, band_dists, career = [], [], [], [], []
    for role in roles:
        m = (r.role == role).to_numpy()
        g = r[m]
        prev = X[m].mean(0)
        skill_vecs.append(prev)
        fam = np.array([g[f"has_{f}"].mean() for f in FAMILIES])
        fam_vecs.append(fam)
        bd = np.bincount(g.band.astype(int), minlength=len(BAND_ORDER)) / len(g)
        band_dists.append(bd)
        career.append([g.exp_min.mean(), g.band.mean()])
        lift = prev / np.where(overall_prev == 0, 1, overall_prev)
        order = np.argsort(-prev)[:15]
        distinctive = [j for j in np.argsort(-(lift * (prev >= 0.05))) if prev[j] >= 0.05][:10]
        p = {"role": role, "group": groups[role], "n": int(m.sum()),
             "pct_of_postings": round(100 * m.sum() / len(a), 2),
             "senior_share": round(float(g.senior.mean()), 3),
             "exp_min_mean": round(float(g.exp_min.mean()), 2), "exp_min_median": float(g.exp_min.median()),
             "exp_max_mean": round(float(g.exp_max.mean()), 2),
             "band_mean": round(float(g.band.mean()), 3), "band_median": BAND_ORDER[int(g.band.median())],
             "band_distribution": [round(float(v), 4) for v in bd],
             "family_prevalence": {f: round(float(v), 4) for f, v in zip(FAMILIES, fam)},
             "family_emphasis": {f: round(float(np.log((v + 0.01) / (o + 0.01))), 4)
                                 for f, v, o in zip(FAMILIES, fam, overall_fam)},
             "top_skills": [{"skill": vocab[j], "prevalence": round(float(prev[j]), 4),
                             "lift": round(float(lift[j]), 2)} for j in order],
             "distinctive_skills": [{"skill": vocab[j], "prevalence": round(float(prev[j]), 4),
                                     "lift": round(float(lift[j]), 2)} for j in distinctive],
             "top_cities": g.city_primary.value_counts().head(5).to_dict(),
             "example_titles": g.job_desig.value_counts().head(6).index.tolist()}
        if role in DSJOBS_TITLES:
            s = d[d.job_title.isin(DSJOBS_TITLES[role])]
            w = s.num_of_jobs.clip(lower=1)
            p["dsjobs"] = {"titles": DSJOBS_TITLES[role], "records": int(len(s)), "postings": int(s.num_of_jobs.sum()),
                           "avg_salary_lakhs": round(float(np.average(s.avg_salary, weights=w)), 2),
                           "min_salary_lakhs": round(float(np.average(s.min_salary, weights=w)), 2),
                           "max_salary_lakhs": round(float(np.average(s.max_salary, weights=w)), 2),
                           "min_experience_mean": round(float(s.min_experience.mean()), 2),
                           "by_title": s.groupby("job_title").agg(avg_salary=("avg_salary", "mean"),
                                                                  min_exp=("min_experience", "mean"),
                                                                  postings=("num_of_jobs", "sum"))
                                        .round(2).reset_index().to_dict("records")}
        profiles.append(p)

    # ---------------- distance views
    S, F, B, C = map(np.array, (skill_vecs, fam_vecs, band_dists, career))
    n = len(roles)
    D_skill = np.array([[_cos_dist(S[i], S[j]) for j in range(n)] for i in range(n)])
    D_comp = squareform(pdist(F, "euclidean"))
    D_sal = np.array([[float(jensenshannon(B[i], B[j], base=2)) for j in range(n)] for i in range(n)])
    Cz = (C - C.mean(0)) / C.std(0)
    D_car = squareform(pdist(Cz, "euclidean"))
    D_blend = np.mean([M / M.max() for M in (D_skill, D_comp, D_sal, D_car)], axis=0)
    views = {
        "skills": {"label": "Skill overlap", "metric": "cosine distance on skill-prevalence vectors",
                   "range": "0 = identical skill mix, 1 = no shared skills", **_view(D_skill, roles)},
        "competency": {"label": "Competency mix", "metric": "Euclidean distance on 5 competency-family prevalences",
                       "range": "0 = same mix; larger = further apart", **_view(D_comp, roles)},
        "salary": {"label": "Salary distribution", "metric": "Jensen-Shannon distance between salary-band distributions",
                   "range": "0 = same pay distribution, 1 = no overlap", **_view(D_sal, roles)},
        "career": {"label": "Experience & pay", "metric": "Euclidean distance on z-scored (mean experience, mean band)",
                   "range": "0 = same seniority & pay level", **_view(D_car, roles)},
        "blended": {"label": "Blended", "metric": "mean of the four distances, each rescaled to 0-1",
                    "range": "0 = alike on every view", **_view(D_blend, roles)},
    }
    for k, v in views.items():
        print(f"  view {k:<10} MDS stress-1 = {v['stress1']}")

    # ---------------- pairwise tests (Holm across all pairs, per test family)
    rng = np.random.default_rng(SEED)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            mi, mj = (r.role == roles[i]).to_numpy(), (r.role == roles[j]).to_numpy()
            obs, p_emp, z, p_z = _perm_skill_test(X[mi], X[mj], rng)
            gi, gj = r[mi], r[mj]
            pairs.append({"a": roles[i], "b": roles[j], "skill_cosine_distance": round(obs, 4),
                          "skill_perm_p_empirical": p_emp, "skill_perm_z": round(z, 2), "skill_perm_p": p_z,
                          "band_diff": round(float(gi.band.mean() - gj.band.mean()), 3),
                          "band_mwu_p": float(stats.mannwhitneyu(gi.band, gj.band).pvalue),
                          "exp_diff": round(float(gi.exp_min.mean() - gj.exp_min.mean()), 3),
                          "exp_mwu_p": float(stats.mannwhitneyu(gi.exp_min, gj.exp_min).pvalue)})
    for key in ["skill_perm_p", "band_mwu_p", "exp_mwu_p"]:
        adj = multipletests([p[key] for p in pairs], method="holm")[1]
        for p, h in zip(pairs, adj):
            p[key[:-2] + "_holm_p"] = float(h)
    print(f"  {len(pairs)} role pairs tested ({N_PERM} permutations each for skills)")

    out = {"roles": roles, "groups": [groups[x] for x in roles], "profiles": profiles, "views": views,
           "pairs": pairs, "skill_vocab": vocab, "skill_prevalence": np.round(S, 4).tolist(), "families": FAMILIES, "family_labels": FAMILY_LABELS, "family_to_jds": FAMILY_TO_JDS,
           "bands": BAND_ORDER, "overall_family_prevalence": {f: round(float(v), 4) for f, v in zip(FAMILIES, overall_fam)},
           "coverage": {"mapped": int(len(r)), "analytics_postings": int(len(a)), "min_postings": MIN_POSTINGS,
                        "unmapped_top_titles": a[a.role.isna()].job_desig.value_counts().head(10).to_dict()},
           "rules": [{"role": nm, "group": g, "regex": p} for nm, g, p in ROLE_RULES]}
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "profiles.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"  saved profiles.json to {ART}")
    return out


if __name__ == "__main__":
    run()
