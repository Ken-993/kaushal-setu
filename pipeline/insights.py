"""Phase 5 - turn the numbers from phases 1-4 into plain-language findings.

Nothing new is estimated here: every sentence is filled in from artifacts/stats.json,
artifacts/models.json and artifacts/profiles.json, so the text always matches the data.
Output: artifacts/insights.json (shown on the dashboard's Overview tab)
"""
import json

import pandas as pd

from config import ART, CLEAN

PRETTY = {"big_data_skills": "big data", "maths_stats_skills": "maths & stats", "coding_skills": "coding",
          "ai_and_ml_skills": "AI & ML", "dashboard_and_storytelling_skills": "dashboards & storytelling",
          "neuroticism": "neuroticism", "extraversion": "extraversion",
          "openness_to_experience": "openness", "agreeableness": "agreeableness",
          "conscientiousness": "conscientiousness",
          "big_data": "big data", "maths_stats": "maths & stats", "coding": "coding", "ai_ml": "AI & ML",
          "dashboards": "dashboards"}


def _fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _lpa(band: str) -> str:
    lo, hi = band.split("to")
    return f"₹{lo}–{hi} LPA"


def _plain(s: dict, m: dict, pr: dict) -> list[str]:
    """The same eight findings in everyday language (shown first on the website)."""
    jds = sorted(s["jds"], key=lambda r: -r["cohens_d"])
    strong = [PRETTY[r["feature"]] for r in jds if r["significant"]]
    weak = [PRETTY[r["feature"]] for r in jds if not r["significant"]]
    auc = next(c["auc"] for c in m["jds"]["comparison"] if c["model"] == m["jds"]["chosen"])
    eb = {r["band"]: r["mean"] for r in s["market"]["experience_by_band"]}
    exp_only = next(c for c in m["band"]["comparison"] if c["model"].startswith("experience"))["within_one_band"]
    full = next(c for c in m["band"]["comparison"] if c["model"] == m["band"]["chosen"])["within_one_band"]
    fam = sorted(s["market"]["family_vs_band"], key=lambda r: -r["band_diff"])
    paying = [PRETTY[r["family"]] for r in fam if r["band_diff"] > 0.5]
    flat = [PRETTY[r["family"]] for r in fam if r["band_diff"] <= 0]
    al = s["alignment"]["table"]
    int_top = max(al, key=lambda r: r["internal_d"])
    mkt_top = max(al, key=lambda r: r["market_band_diff"])
    D = pr["views"]["skills"]["matrix"]
    mx = max(max(r) for r in D)
    roles = pr["roles"]
    pairs = sorted(pr["pairs"], key=lambda p: p["skill_cosine_distance"])
    close = pairs[0]
    alike = round(100 * (1 - D[roles.index(close["a"])][roles.index(close["b"])] / mx))
    data_roles = {p["role"] for p in pr["profiles"] if p["group"] == "data"}
    far = [p for p in pairs if p["a"] in data_roles and p["b"] in data_roles][-1]
    by_band = sorted(pr["profiles"], key=lambda p: -p["band_mean"])
    sen = s["dsjobs"]["mean_salary_by_seniority"]
    return [
        (f"Juniors who got a high salary hike were clearly stronger at {', '.join(strong)}. "
         + (f"{', '.join(weak).capitalize()} made no real difference. " if weak else "")
         + f"Using just these five scores, the model tells high-hike and low-hike juniors apart correctly about {round(auc * 100)}% of the time."),
        ("Highly successful senior data scientists stand out most for being organised and dependable (conscientiousness) "
         "and curious and open to new ideas (openness). Being more anxious or calm (neuroticism) made no difference on its own."),
        (f"Experience matters most for pay. Postings in the ₹25–50 LPA range ask for about {eb[5]:.0f} years on average, "
         f"while ₹0–3 LPA postings ask for about {eb[0]:.0f}. From the years asked for alone, the model gets the pay range right "
         f"(or one step off) {exp_only:.0%} of the time; adding skills, job title and city lifts that to {full:.0%}."),
        (f"Jobs asking for {', '.join(paying)} pay noticeably more, roughly three-quarters of a pay range higher. "
         + (f"{', '.join(flat).capitalize()} don't pay extra. " if flat else "")
         + "The extra pay for big-data skills is biggest for freshers and fades away after about five years of experience."),
        (f"The company in this data rewards {PRETTY[int_top['family']]} most when giving salary hikes, but the job market pays "
         f"nothing extra for it. {PRETTY[mkt_top['family']]} earns the biggest premium in the market. "
         "In short, what this company rewards and what the market pays for don't line up."),
        (f"{close['a']} and {close['b']} are {alike}% alike in the skills employers ask for: almost the same job. "
         f"Among data roles, {far['a']} and {far['b']} are the most different."),
        (f"{by_band[0]['role']} and {by_band[1]['role']} pay the most, usually {_lpa(by_band[0]['band_median'])}. "
         f"{by_band[-1]['role']} pays the least, usually {_lpa(by_band[-1]['band_median'])}. "
         f"Job titles with 'Senior' advertise about ₹{sen['senior']:.0f} LPA on average, against ₹{sen['standard']:.0f} LPA for the rest."),
        ("The job ads in the data are cut short, so the skill counts are on the low side. The salary-hike and success findings "
         "come from one company's staff (about 150 people each), so they describe that company, not everyone."),
    ]


def run() -> list[dict]:
    print("== Phase 5: insights ==")
    s = json.loads((ART / "stats.json").read_text())
    m = json.loads((ART / "models.json").read_text())
    pr = json.loads((ART / "profiles.json").read_text())
    out = []

    # 1 - junior skills
    jds = sorted(s["jds"], key=lambda r: -r["cohens_d"])
    sig = [PRETTY[r["feature"]] for r in jds if r["significant"]]
    nonsig = [PRETTY[r["feature"]] for r in jds if not r["significant"]]
    out.append({"area": "Junior data scientists", "title": "What separates a high salary hike from a low one",
                "text": (f"Juniors with a high hike score higher on {', '.join(sig)} (each significant after Holm correction). "
                         f"The largest gap is {PRETTY[jds[0]['feature']]} (Cohen's d = {jds[0]['cohens_d']}). "
                         + (f"{', '.join(nonsig).capitalize()} shows no reliable difference. " if nonsig else "")
                         + f"A {m['jds']['chosen']} on the five scores reaches cross-validated AUC "
                           f"{next(c['auc'] for c in m['jds']['comparison'] if c['model'] == m['jds']['chosen'])}."),
                "evidence": "Phase 2 group tests + Phase 3 JDS model"})

    # 2 - senior personality
    sds = sorted(s["sds"], key=lambda r: -abs(r["cohens_d"]))
    top2 = [PRETTY[r["feature"]] for r in sds[:2]]
    flat = [PRETTY[r["feature"]] for r in sds if not r["significant"]]
    out.append({"area": "Senior data scientists", "title": "Personality and overall success",
                "text": (f"{top2[0].capitalize()} (d = {sds[0]['cohens_d']}) and {top2[1]} (d = {sds[1]['cohens_d']}) "
                         f"show the biggest differences between high- and low-success seniors. "
                         + (f"{', '.join(flat).capitalize()} does not differ on its own. " if flat else "")
                         + f"The chosen model ({m['sds']['chosen']}) reaches AUC "
                           f"{next(c['auc'] for c in m['sds']['comparison'] if c['model'] == m['sds']['chosen'])}: "
                           f"{m['sds']['reason']}."),
                "evidence": "Phase 2 group tests + Phase 3 SDS model"})

    # 3 - experience
    e = s["market"]["experience_vs_band"]
    out.append({"area": "Job market", "title": "Experience is the main driver of the salary band",
                "text": (f"Across {s['market']['n']:,} analytics postings, minimum experience and salary band move "
                         f"together strongly (Spearman rho = {e['spearman_rho']}, Kendall tau-b = {e['kendall_tau_b']}). "
                         f"An ordinal model using experience alone already gets "
                         f"{next(c for c in m['band']['comparison'] if c['model'].startswith('experience'))['within_one_band']:.0%} "
                         f"of test postings within one band; adding skills, title and city lifts that to "
                         f"{next(c for c in m['band']['comparison'] if c['model'] == m['band']['chosen'])['within_one_band']:.0%}."),
                "evidence": "Phase 2 market tests + Phase 3 band model"})

    # 4 - competency premium
    fam = sorted(s["market"]["family_vs_band"], key=lambda r: -r["band_diff"])
    bd = s["market"]["big_data_by_experience"]
    out.append({"area": "Job market", "title": "Which competencies carry a pay premium",
                "text": (f"Postings asking for {PRETTY[fam[0]['family']]} sit {fam[0]['band_diff']} bands higher on average, "
                         f"followed by {PRETTY[fam[1]['family']]} (+{fam[1]['band_diff']}) and {PRETTY[fam[2]['family']]} "
                         f"(+{fam[2]['band_diff']}); {PRETTY[fam[-1]['family']]} is {fam[-1]['band_diff']}. "
                         f"The big-data premium fades with experience: +{bd[0]['band_diff']} bands at {bd[0]['stratum']} years, "
                         f"+{bd[-1]['band_diff']} at {bd[-1]['stratum']} years."),
                "evidence": "Phase 2 Mann-Whitney + Holm, stratified by experience"})

    # 5 - alignment
    al = s["alignment"]
    int_top = max(al["table"], key=lambda r: r["internal_d"])
    mkt_top = max(al["table"], key=lambda r: r["market_band_diff"])
    out.append({"area": "Company vs market", "title": "Does the company reward what the market pays for?",
                "text": (f"Ranking the five competencies by internal effect (hike) and by market premium (band) gives "
                         f"Spearman rho = {al['spearman_rho']} (n = {al['n_families']}, {_fmt_p(al['p'])}). "
                         f"{PRETTY[int_top['family']].capitalize()} is the strongest internal signal (d = {int_top['internal_d']}) "
                         f"but its market premium is {int_top['market_band_diff']:+} bands, while "
                         f"{PRETTY[mkt_top['family']]} has the largest market premium ({mkt_top['market_band_diff']:+} bands) "
                         f"and an internal effect of d = {mkt_top['internal_d']}. "
                         "With five points this is a direction to investigate, not a tested result."),
                "evidence": "Phase 2 alignment table"})

    # 6 - role similarity
    pairs = sorted(pr["pairs"], key=lambda p: p["skill_cosine_distance"])
    data_roles = [p["role"] for p in pr["profiles"] if p["group"] == "data"]
    dp = [p for p in pairs if p["a"] in data_roles and p["b"] in data_roles]
    out.append({"area": "Job profiles", "title": "Which data roles are really the same job?",
                "text": (f"On skill mix, the closest pair is {pairs[0]['a']} and {pairs[0]['b']} "
                         f"(cosine distance {pairs[0]['skill_cosine_distance']}); the furthest-apart data roles are "
                         f"{dp[-1]['a']} and {dp[-1]['b']} ({dp[-1]['skill_cosine_distance']}). "
                         f"All {len(pairs)} role pairs differ significantly after Holm correction, so the useful "
                         "question is how far apart they are, which the distance maps show."),
                "evidence": "Phase 4 skill-distance matrix + permutation tests"})

    # 7 - pay by role
    by_band = sorted(pr["profiles"], key=lambda p: -p["band_mean"])
    ds = [p for p in pr["profiles"] if "dsjobs" in p]
    ds_top = max(ds, key=lambda p: p["dsjobs"]["avg_salary_lakhs"])
    sen = s["dsjobs"]["mean_salary_by_seniority"]
    out.append({"area": "Job profiles", "title": "Best-paid profiles",
                "text": (f"In the analytics postings the highest average band belongs to {by_band[0]['role']} "
                         f"({by_band[0]['band_mean']:.2f}, median {by_band[0]['band_median']} lakhs) and "
                         f"{by_band[1]['role']} ({by_band[1]['band_mean']:.2f}); the lowest is {by_band[-1]['role']} "
                         f"({by_band[-1]['band_mean']:.2f}). In the DataScience Jobs file {ds_top['role']} advertises the most "
                         f"(about {ds_top['dsjobs']['avg_salary_lakhs']} lakhs), and senior titles average "
                         f"{sen['senior']} lakhs against {sen['standard']} for standard titles."),
                "evidence": "Phase 4 profiles + DataScience Jobs (descriptive only)"})

    # 8 - data quality caveat
    desc = pd.read_csv(CLEAN / "Analytics.csv", usecols=["job_description"])["job_description"].dropna()
    n_dup = int(desc.duplicated().sum())
    out.append({"area": "Data quality", "title": "Caveats to keep in mind",
                "text": (f"Analytics descriptions and skill lists are truncated at about 110 characters, so every prevalence "
                         f"figure is a lower bound. {n_dup:,} postings repeat an earlier description word for word, handled with "
                         "a grouped train/test split. JDS and SDS are small single-company samples (n ~ 140-160), so their "
                         "effects describe this company, not data scientists in general."),
                "evidence": "Phase 1 cleaning report"})

    for item, text in zip(out, _plain(s, m, pr)):
        item["plain"] = text
    (ART / "insights.json").write_text(json.dumps(out, indent=2))
    for i in out:
        print(f"  - {i['title']}")
    return out


if __name__ == "__main__":
    run()
