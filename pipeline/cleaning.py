"""Phase 1 - load, audit and clean the four official datasets.

Every non-trivial decision is appended to LOG so it can be shown in the API
and in the final report (nothing is silently dropped).
"""
import hashlib
import json
import re

import numpy as np
import pandas as pd

from config import BAND_MAP, CLEAN, RAW, TAXONOMY

LOG: list[dict] = []


def log(dataset: str, decision: str, detail: str):
    LOG.append({"dataset": dataset, "decision": decision, "detail": detail})
    print(f"  [{dataset}] {decision}: {detail}")


def _snake(cols):
    out = []
    for c in cols:
        c = str(c).strip().lower()
        c = re.sub(r"[^a-z0-9]+", "_", c).strip("_")
        out.append(c)
    return out


# ----------------------------------------------------------------- JDS / SDS
def clean_jds() -> pd.DataFrame:
    df = pd.read_excel(RAW / "JDS_Skill_Traits.xlsx")
    df.columns = _snake(df.columns)  # maths-stats_skills -> maths_stats_skills
    df = df.rename(columns={"salary_hike_high_or_low": "target"})
    log("JDS", "rename columns", "snake_case; outcome renamed to 'target' (1=high hike)")
    dup_ids = int(df["id"].duplicated().sum())
    log("JDS", "duplicate ids kept",
        f"{dup_ids} repeated id value(s); rows differ in measurements so they are distinct observations. id excluded from models.")
    out_of_range = int(((df.drop(columns=["id", "target"]) < 1) | (df.drop(columns=["id", "target"]) > 5)).sum().sum())
    log("JDS", "range check", f"{out_of_range} scores outside documented 1-5 scale")
    return df


def clean_sds() -> pd.DataFrame:
    df = pd.read_excel(RAW / "SDS_Personality_Traits.xlsx")
    df.columns = _snake(df.columns)  # ' extraversion' -> 'extraversion'
    df = df.rename(columns={"success_classification_high_low": "target"})
    log("SDS", "rename columns",
        "stripped leading space in ' extraversion'; fixed 'success_ classification_ high_low' -> 'target'")
    log("SDS", "duplicate ids kept", f"{int(df['id'].duplicated().sum())} repeated id value(s); distinct rows, kept; id excluded from models.")
    return df


# ------------------------------------------------------------ DataScience Jobs
def _lakhs(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace("L", "", regex=False).str.strip(), errors="coerce")


def clean_dsjobs() -> pd.DataFrame:
    df = pd.read_csv(RAW / "DataScience_Jobs.csv")
    for c in ["avg_salary", "min_salary", "max_salary"]:
        df[c] = _lakhs(df[c])
    bad = int(df[["avg_salary", "min_salary", "max_salary"]].isna().sum().sum())
    log("DSJobs", "salary parse", f"'7.8L' -> 7.8 (lakhs). unparseable cells: {bad}")
    ordered = bool(((df.min_salary <= df.avg_salary) & (df.avg_salary <= df.max_salary)).all())
    log("DSJobs", "ordering check", f"min <= avg <= max holds for all rows: {ordered}")
    corr = float(np.corrcoef((df.min_salary + df.max_salary) / 2, df.avg_salary)[0, 1])
    log("DSJobs", "leakage warning",
        f"(min+max)/2 correlates {corr:.3f} with avg_salary -> file is descriptive only; never model avg from min/max.")
    log("DSJobs", "duplicate ids kept", f"{int(df['reference_no'].duplicated().sum())} repeated reference_no; kept.")
    df["seniority"] = np.where(df.job_title.str.contains("senior|sr\\.?|lead|principal", case=False, regex=True), "senior", "standard")
    return df


# ------------------------------------------------------------- Analytics Jobs
def _parse_experience(s: str):
    m = re.findall(r"\d+", str(s))
    if len(m) >= 2:
        return int(m[0]), int(m[1])
    if len(m) == 1:
        return int(m[0]), int(m[0])
    return np.nan, np.nan


NON_ANALYTICS = re.compile(
    r"data entry|work from home|freelanc|typist|back office|form filling|copy paste", re.I)

LOC_ALIASES = {"gurugram": "gurgaon", "bangalore": "bengaluru", "bombay": "mumbai",
               "madras": "chennai", "calcutta": "kolkata"}


def _norm_locations(s: str) -> str:
    parts = [p.strip().lower() for p in str(s).split(",") if p.strip()]
    parts = [LOC_ALIASES.get(p, p) for p in parts]
    return ", ".join(dict.fromkeys(parts))


def _match_family(tokens: list[str], keywords: list[str]) -> bool:
    for kw in keywords:
        for t in tokens:
            if len(kw) <= 3:
                if t == kw or re.search(rf"\b{re.escape(kw)}\b", t):
                    return True
            elif kw in t:
                return True
    return False


def clean_analytics() -> pd.DataFrame:
    df = pd.read_csv(RAW / "Analytics_Jobs.csv")
    n0 = len(df)

    # experience free text -> numeric bounds
    bounds = df["experience"].apply(_parse_experience)
    df["exp_min"] = [b[0] for b in bounds]
    df["exp_max"] = [b[1] for b in bounds]
    df["exp_span"] = df.exp_max - df.exp_min
    log("Analytics", "experience parse",
        f"parsed {int(df.exp_min.notna().sum())}/{n0} rows; inverted ranges: {int((df.exp_span < 0).sum())}")

    # ordinal target
    df["band"] = df["salary"].map(BAND_MAP)
    log("Analytics", "ordinal target", f"salary -> band 0..5; unmapped: {int(df.band.isna().sum())}")

    # truncation facts + the '...' artifact
    desc = df["job_description"].dropna()
    log("Analytics", "truncation",
        f"{int(desc.str.endswith('...').sum())} descriptions end with '...' (max len {int(desc.str.len().max())}); "
        "skill lists truncated too -> prevalence figures are lower bounds; no full-text NLP.")

    # skills: tokenise, drop the '...' artifact and truncated partial tokens
    df["key_skills"] = df["key_skills"].fillna("")
    raw_toks = df["key_skills"].apply(lambda s: [t.strip() for t in s.split(",") if t.strip()])
    n_dots = int(sum(t == "..." for toks in raw_toks for t in toks))
    n_partial = int(sum(t.endswith("...") and t != "..." for toks in raw_toks for t in toks))
    df["skill_tokens"] = raw_toks.apply(lambda toks: [t.lower() for t in toks if not t.endswith("...")])
    log("Analytics", "ellipsis artifact removed",
        f"{n_dots} stand-alone '...' tokens removed (would otherwise be a top 'skill'). "
        f"{n_partial} cut-off last tokens (e.g. 'Rest...') dropped as partial -> conservative, prevalence is a lower bound.")

    # job type: fold casing, explicit missing level
    miss = float(df.job_type.isna().mean())
    df["job_type"] = df.job_type.fillna("not stated").str.strip().str.lower()
    log("Analytics", "job_type", f"{miss:.1%} missing -> explicit 'not stated' level (not imputed); casing folded.")

    # location aliases
    df["location_clean"] = df.location.apply(_norm_locations)
    df["city_primary"] = df.location_clean.str.split(",").str[0].str.strip()
    log("Analytics", "location aliases", "Gurugram->Gurgaon, Bangalore->Bengaluru etc. merged; Noida kept separate.")

    # non-analytics flag (flag, don't delete)
    df["non_analytics"] = (df.job_desig.str.contains(NON_ANALYTICS) |
                           df.job_description.fillna("").str.contains(NON_ANALYTICS))
    log("Analytics", "non-analytics flag", f"{int(df.non_analytics.sum())} data-entry / WFH / freelance posts flagged by regex (kept in file, excluded from modelling). Regex is a judgement call; counts differ with wording.")

    # leakage control: group key from description hash
    def _grp(row):
        d = row["job_description"]
        if pd.isna(d):
            return f"na_{row.name}"  # missing descriptions are not duplicates of each other
        return hashlib.md5(str(d).encode()).hexdigest()
    df["desc_group"] = df.apply(_grp, axis=1)
    dup = int(df["job_description"].dropna().duplicated().sum())
    log("Analytics", "duplicate descriptions", f"{dup} exact duplicate descriptions -> desc_group key for grouped train/test split.")

    # competency-family flags via taxonomy (token-level)
    for fam, kws in TAXONOMY.items():
        df[f"has_{fam}"] = df["skill_tokens"].apply(lambda toks: _match_family(toks, kws))
    all_toks = pd.Series([t for toks in df.skill_tokens for t in toks])
    mapped = all_toks.apply(lambda t: any(_match_family([t], kws) for kws in TAXONOMY.values()))
    log("Analytics", "taxonomy",
        f"5 competency flags built from tokens; {mapped.mean():.1%} of all skill-token occurrences map to a competency "
        "(rest are out-of-scope skills such as finance, SEO). Taxonomy is a documented judgement - see config.TAXONOMY.")
    return df


# ------------------------------------------------------------------- driver
def audit(frames: dict[str, pd.DataFrame]) -> list[dict]:
    rows = []
    for name, df in frames.items():
        idcol = {"JDS": "id", "SDS": "id", "DSJobs": "reference_no", "Analytics": "s_no"}[name]
        rows.append({
            "dataset": name, "rows": len(df), "cols": df.shape[1],
            "missing_cells": int(df.drop(columns=[c for c in ["skill_tokens"] if c in df]).isna().sum().sum()),
            "row_duplicates": int(df.drop(columns=[c for c in ["skill_tokens"] if c in df]).astype(str).duplicated().sum()),
            "dup_ids": int(df[idcol].duplicated().sum()),
        })
    return rows


def run() -> dict[str, pd.DataFrame]:
    LOG.clear()
    CLEAN.mkdir(parents=True, exist_ok=True)
    print("== Phase 1: cleaning ==")
    frames = {"JDS": clean_jds(), "SDS": clean_sds(), "DSJobs": clean_dsjobs(), "Analytics": clean_analytics()}
    for name, df in frames.items():
        out = df.copy()
        if "skill_tokens" in out:
            out["skill_tokens"] = out["skill_tokens"].apply(lambda t: "|".join(t))
        out.to_csv(CLEAN / f"{name}.csv", index=False)
    report = {"audit": audit(frames), "decisions": LOG}
    (CLEAN / "cleaning_report.json").write_text(json.dumps(report, indent=2))
    print(f"  saved cleaned files + cleaning_report.json to {CLEAN}")
    return frames


if __name__ == "__main__":
    run()
