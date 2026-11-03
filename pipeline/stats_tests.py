"""Phase 2 - assumption-driven statistics (no models here, just tests)."""
import json
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from config import ART, JDS_FEATURES, SDS_FEATURES, SEED

warnings.filterwarnings("ignore")
FAMILIES = ["big_data", "maths_stats", "coding", "ai_ml", "dashboards"]
FAMILY_TO_JDS = dict(zip(FAMILIES, JDS_FEATURES))


def cohens_d(a, b):
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    d = (a.mean() - b.mean()) / sp
    se = np.sqrt((na + nb) / (na * nb) + d ** 2 / (2 * (na + nb)))
    return float(d), (float(d - 1.96 * se), float(d + 1.96 * se))


def group_comparison(df: pd.DataFrame, features: list[str]) -> list[dict]:
    """High vs low group on each feature; test chosen by Shapiro + Levene; Holm across the family."""
    rows = []
    for f in features:
        hi, lo = df.loc[df.target == 1, f], df.loc[df.target == 0, f]
        normal = bool(stats.shapiro(hi).pvalue > 0.05 and stats.shapiro(lo).pvalue > 0.05)
        lev_p = float(stats.levene(hi, lo).pvalue)
        if normal:
            test, p = "Welch t", float(stats.ttest_ind(hi, lo, equal_var=False).pvalue)
        else:
            test, p = "Mann-Whitney U", float(stats.mannwhitneyu(hi, lo, alternative="two-sided").pvalue)
        d, ci = cohens_d(hi, lo)
        rows.append({"feature": f, "mean_low": round(float(lo.mean()), 3), "mean_high": round(float(hi.mean()), 3),
                     "normal": normal, "levene_p": round(lev_p, 4), "test": test, "p": p,
                     "cohens_d": round(d, 3), "ci_low": round(ci[0], 3), "ci_high": round(ci[1], 3)})
    holm = multipletests([r["p"] for r in rows], method="holm")[1]
    for r, hp in zip(rows, holm):
        r["holm_p"] = float(hp)
        r["significant"] = bool(hp < 0.05)
    return rows


def market_stats(a: pd.DataFrame) -> dict:
    """a = cleaned Analytics Jobs, already filtered to analytics postings."""
    out = {"n": int(len(a))}

    # RQ3: experience vs band
    rho, p = stats.spearmanr(a.exp_min, a.band)
    tau = stats.kendalltau(a.exp_min, a.band)[0]
    H, kp = stats.kruskal(*[g.exp_min.values for _, g in a.groupby("band")])
    out["experience_vs_band"] = {"spearman_rho": round(float(rho), 3), "kendall_tau_b": round(float(tau), 3),
                                 "kruskal_epsilon_sq": round(float(H / (len(a) - 1)), 3), "p": float(p)}
    out["experience_by_band"] = (a.groupby("band").exp_min.agg(["count", "mean", "median", "std"]).round(2)
                                 .reset_index().to_dict("records"))

    # RQ4a: competency families vs band (MWU + Holm), with Cohen's d
    fam_rows = []
    for fam in FAMILIES:
        w, wo = a.loc[a[f"has_{fam}"], "band"], a.loc[~a[f"has_{fam}"], "band"]
        if len(w) < 30 or len(wo) < 30:
            continue
        d, _ = cohens_d(w.astype(float), wo.astype(float))
        p = float(stats.mannwhitneyu(w, wo, alternative="two-sided").pvalue)
        fam_rows.append({"family": fam, "n_with": int(len(w)), "pct_postings": round(100 * len(w) / len(a), 2),
                         "band_diff": round(float(w.mean() - wo.mean()), 3), "cohens_d": round(d, 3), "p": p})
    holm = multipletests([r["p"] for r in fam_rows], method="holm")[1]
    for r, hp in zip(fam_rows, holm):
        r["holm_p"] = float(hp)
    out["family_vs_band"] = fam_rows

    # RQ4b: individual skill tokens (>=150 postings), MWU + Holm
    from collections import Counter
    cnt = Counter(t for toks in a.skill_tokens for t in set(toks))
    skills = [s for s, c in cnt.most_common(400) if c >= 150][:20]
    tok_sets = a.skill_tokens.apply(set)
    sk_rows = []
    for s in skills:
        m = tok_sets.apply(lambda x: s in x)
        w, wo = a.loc[m, "band"], a.loc[~m, "band"]
        sk_rows.append({"skill": s, "postings": int(m.sum()), "band_diff": round(float(w.mean() - wo.mean()), 3),
                        "p": float(stats.mannwhitneyu(w, wo, alternative="two-sided").pvalue)})
    holm = multipletests([r["p"] for r in sk_rows], method="holm")[1]
    for r, hp in zip(sk_rows, holm):
        r["holm_p"] = float(hp)
        r["significant"] = bool(hp < 0.05)
    out["top_skills_vs_band"] = sorted(sk_rows, key=lambda r: -r["band_diff"])

    # Big data: adjusted + stratified by experience
    from statsmodels.miscmodels.ordinal_model import OrderedModel
    X = pd.DataFrame({"big_data": a.has_big_data.astype(float), "exp_min": a.exp_min, "exp_span": a.exp_span})
    sub = X.sample(min(len(X), 8000), random_state=SEED)  # subsample keeps the ordinal fit fast
    try:
        res = OrderedModel(a.loc[sub.index, "band"].astype(int), sub, distr="logit").fit(method="bfgs", disp=False)
        coef, se = res.params["big_data"], res.bse["big_data"]
        out["big_data_adjusted"] = {"odds_ratio": round(float(np.exp(coef)), 3),
                                    "ci": [round(float(np.exp(coef - 1.96 * se)), 3), round(float(np.exp(coef + 1.96 * se)), 3)],
                                    "fit_rows": int(len(sub))}
    except Exception as e:  # keep API alive if the optimiser struggles
        out["big_data_adjusted"] = {"error": str(e)}
    strata = [("0-2", 0, 2), ("3-5", 3, 5), ("6-8", 6, 8), ("9+", 9, 99)]
    srows = []
    for name, lo, hi in strata:
        g = a[(a.exp_min >= lo) & (a.exp_min <= hi)]
        w, wo = g.loc[g.has_big_data, "band"], g.loc[~g.has_big_data, "band"]
        if len(w) >= 20:
            srows.append({"stratum": name, "n_with": int(len(w)), "n_without": int(len(wo)),
                          "band_diff": round(float(w.mean() - wo.mean()), 3),
                          "p": float(stats.mannwhitneyu(w, wo).pvalue)})
    out["big_data_by_experience"] = srows

    # Designation association
    top = a.job_desig.value_counts().head(10).index
    ct = pd.crosstab(a.loc[a.job_desig.isin(top), "job_desig"], a.loc[a.job_desig.isin(top), "band"])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    out["designation_vs_band"] = {"top_n": 10, "chi2": round(float(chi2), 1), "dof": int(dof), "p": float(p),
                                  "cramers_v": round(float(np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))), 3)}
    return out


def dsjobs_stats(d: pd.DataFrame) -> dict:
    by_role = (d.groupby("job_title").agg(records=("job_title", "size"), mean_avg_salary=("avg_salary", "mean"),
                                         mean_min_exp=("min_experience", "mean"), postings=("num_of_jobs", "sum"))
               .round(2).sort_values("mean_avg_salary", ascending=False).reset_index())
    prem = d.groupby("seniority").avg_salary.mean().round(2).to_dict()
    comp = d.groupby("company_name").agg(n=("num_of_jobs", "sum"), sal=("avg_salary", "mean"))
    comp = comp[comp.n >= 50]
    rho = stats.spearmanr(comp.n, comp.sal)[0]
    return {"by_role": by_role.to_dict("records"), "mean_salary_by_seniority": prem,
            "volume_vs_salary_spearman": round(float(rho), 3), "companies_with_50plus_postings": int(len(comp))}


def alignment(jds_rows: list[dict], fam_rows: list[dict]) -> dict:
    jd = {r["feature"]: r for r in jds_rows}
    table = []
    for r in fam_rows:
        j = jd[FAMILY_TO_JDS[r["family"]]]
        table.append({"family": r["family"], "internal_d": j["cohens_d"], "internal_holm_p": j["holm_p"],
                      "market_pct": r["pct_postings"], "market_band_diff": r["band_diff"], "market_holm_p": r["holm_p"]})
    t = pd.DataFrame(table)
    rho, p = stats.spearmanr(t.internal_d, t.market_band_diff)
    return {"table": table, "spearman_rho": round(float(rho), 3), "p": round(float(p), 3), "n_families": int(len(t)),
            "note": "Rank comparison across separate populations; with n=5 it is directional only, never a tested result."}


def run(frames: dict) -> dict:
    print("== Phase 2: statistics ==")
    jds, sds = frames["JDS"], frames["SDS"]
    a = frames["Analytics"]
    a = a[~a.non_analytics].copy()
    res = {"jds": group_comparison(jds, JDS_FEATURES), "sds": group_comparison(sds, SDS_FEATURES),
           "market": market_stats(a), "dsjobs": dsjobs_stats(frames["DSJobs"])}
    res["alignment"] = alignment(res["jds"], res["market"]["family_vs_band"])
    ART.mkdir(exist_ok=True, parents=True)
    (ART / "stats.json").write_text(json.dumps(res, indent=2, default=str))
    for r in res["jds"]:
        print(f"  JDS {r['feature']:<36} d={r['cohens_d']:>6}  holm_p={r['holm_p']:.4f}  {r['test']}")
    for r in res["sds"]:
        print(f"  SDS {r['feature']:<36} d={r['cohens_d']:>6}  holm_p={r['holm_p']:.4f}  {r['test']}")
    print("  market:", res["market"]["experience_vs_band"])
    print("  alignment rho:", res["alignment"]["spearman_rho"], "p:", res["alignment"]["p"])
    return res


if __name__ == "__main__":
    from pipeline import cleaning
    run(cleaning.run())
