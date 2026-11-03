"""Phase 3 - predictive models.

Three models, one per question:
  A. JDS  : technical skill scores (1-5)    -> P(high salary hike)   [binary]
  B. SDS  : Big-Five personality scores      -> P(high success)       [binary]
  C. Market: experience + skills + title + city -> salary band 0..5   [ordinal]

Design rules
  * Small samples (JDS n=139, SDS n=161) -> repeated stratified 5-fold CV, never one split.
  * Several candidate models are compared against a dummy baseline. Logistic regression is
    kept unless a black-box model beats its AUC by more than 0.02 (parsimony rule), because
    the API needs to explain every prediction.
  * Analytics postings contain thousands of copy-pasted descriptions, so the train/test split
    is GROUPED on desc_group: the same advert can never sit in both train and test.

Outputs (artifacts/):
  jds_model.joblib, sds_model.joblib, band_model.joblib, models.json
"""
import json
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, cohen_kappa_score, confusion_matrix,
                             mean_absolute_error, roc_auc_score, roc_curve)
from sklearn.model_selection import (GroupKFold, GroupShuffleSplit, RepeatedStratifiedKFold,
                                     StratifiedKFold, cross_val_predict, cross_validate)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config import ART, BAND_ORDER, CLEAN, JDS_FEATURES, SDS_FEATURES, SEED
from pipeline.ordinal import OrdinalLogit, split_pipe

warnings.filterwarnings("ignore")
FAMILY_COLS = ["has_big_data", "has_maths_stats", "has_coding", "has_ai_ml", "has_dashboards"]
NUM_COLS = ["exp_min", "exp_max", "exp_span"]


# =============================================================== A + B: binary
def _binary_candidates():
    return {
        "baseline (majority)": DummyClassifier(strategy="prior"),
        "logistic regression": Pipeline([("scale", StandardScaler()),
                                         ("clf", LogisticRegression(C=1.0, max_iter=2000))]),
        "random forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=3, random_state=SEED),
        "gradient boosting": GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.05,
                                                        random_state=SEED),
    }


def _bootstrap_coefs(X, y, n_boot=500):
    """Bootstrap CI for standardised logistic coefficients (how stable is each effect?)."""
    rng = np.random.default_rng(SEED)
    coefs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        m = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(C=1.0, max_iter=2000))])
        m.fit(X[idx], y[idx])
        coefs.append(m.named_steps["clf"].coef_[0])
    return np.percentile(np.array(coefs), [2.5, 97.5], axis=0)


def fit_binary(name: str, df: pd.DataFrame, features: list[str]) -> dict:
    X, y = df[features].to_numpy(float), df["target"].to_numpy(int)
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=SEED)
    comparison = []
    for cname, model in _binary_candidates().items():
        r = cross_validate(model, X, y, cv=cv, scoring=["roc_auc", "accuracy", "neg_brier_score", "f1"])
        comparison.append({"model": cname,
                           "auc": round(float(r["test_roc_auc"].mean()), 3),
                           "auc_sd": round(float(r["test_roc_auc"].std()), 3),
                           "accuracy": round(float(r["test_accuracy"].mean()), 3),
                           "f1": round(float(r["test_f1"].mean()), 3),
                           "brier": round(float(-r["test_neg_brier_score"].mean()), 3)})
        print(f"  {name:<4} {cname:<22} AUC={comparison[-1]['auc']:.3f}±{comparison[-1]['auc_sd']:.3f} "
              f"acc={comparison[-1]['accuracy']:.3f}")

    real = [c for c in comparison if not c["model"].startswith("baseline")]
    best = max(real, key=lambda c: c["auc"])
    logit = next(c for c in real if c["model"] == "logistic regression")
    chosen = "logistic regression" if best["auc"] - logit["auc"] <= 0.02 else best["model"]
    reason = ("logistic regression is within 0.02 AUC of the best model, so the interpretable model is kept"
              if chosen == "logistic regression" else
              f"{chosen} beats logistic regression by {best['auc'] - logit['auc']:.3f} AUC")

    final = _binary_candidates()[chosen]
    # out-of-fold predictions -> honest ROC curve + confusion matrix for the dashboard
    oof = cross_val_predict(final, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED),
                            method="predict_proba")[:, 1]
    fpr, tpr, _ = roc_curve(y, oof)
    cm = confusion_matrix(y, (oof >= 0.5).astype(int)).tolist()
    final.fit(X, y)

    # always report the logistic coefficients (they are the explanation layer of the API)
    lr = _binary_candidates()["logistic regression"].fit(X, y)
    ci = _bootstrap_coefs(X, y)
    coefs = [{"feature": f, "coef_std": round(float(c), 3), "odds_ratio_per_sd": round(float(np.exp(c)), 3),
              "ci_low": round(float(lo), 3), "ci_high": round(float(hi), 3)}
             for f, c, lo, hi in zip(features, lr.named_steps["clf"].coef_[0], ci[0], ci[1])]
    perm = permutation_importance(final, X, y, scoring="roc_auc", n_repeats=30, random_state=SEED)
    importance = sorted([{"feature": f, "auc_drop": round(float(m), 4), "sd": round(float(s), 4)}
                         for f, m, s in zip(features, perm.importances_mean, perm.importances_std)],
                        key=lambda r: -r["auc_drop"])

    joblib.dump({"model": final, "explainer": lr, "features": features, "chosen": chosen},
                ART / f"{name.lower()}_model.joblib")
    step = max(1, len(fpr) // 60)
    return {"n": int(len(y)), "positive_rate": round(float(y.mean()), 3), "features": features,
            "comparison": comparison, "chosen": chosen, "reason": reason,
            "oof_auc": round(float(roc_auc_score(y, oof)), 3),
            "roc": {"fpr": [round(float(v), 3) for v in fpr[::step]] + [1.0],
                    "tpr": [round(float(v), 3) for v in tpr[::step]] + [1.0]},
            "confusion_matrix": cm, "coefficients": coefs, "permutation_importance": importance,
            "feature_means": {f: round(float(v), 3) for f, v in zip(features, X.mean(0))},
            "feature_sds": {f: round(float(v), 3) for f, v in zip(features, X.std(0, ddof=1))},
            "feature_min": {f: round(float(v), 3) for f, v in zip(features, X.min(0))},
            "feature_max": {f: round(float(v), 3) for f, v in zip(features, X.max(0))}}


# ================================================================ C: ordinal
def band_preprocessor(min_df_skills: int = 15) -> ColumnTransformer:
    return ColumnTransformer([
        ("num", StandardScaler(), NUM_COLS),
        ("skills", CountVectorizer(tokenizer=split_pipe, lowercase=False, token_pattern=None,
                                   binary=True, min_df=min_df_skills), "skill_tokens"),
        ("title", TfidfVectorizer(ngram_range=(1, 2), min_df=10, sublinear_tf=True), "job_desig"),
        ("city", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=30), ["city_primary"]),
        ("family", "passthrough", FAMILY_COLS),
    ])


def band_frame(a: pd.DataFrame) -> pd.DataFrame:
    X = a[NUM_COLS + ["skill_tokens", "job_desig", "city_primary"] + FAMILY_COLS].copy()
    X["skill_tokens"] = X["skill_tokens"].fillna("").astype(str)
    X["job_desig"] = X["job_desig"].fillna("").astype(str).str.lower()
    X["city_primary"] = X["city_primary"].fillna("unknown").astype(str)
    X[FAMILY_COLS] = X[FAMILY_COLS].astype(int)
    return X


def _ord_metrics(y, pred) -> dict:
    return {"accuracy": round(float(accuracy_score(y, pred)), 3),
            "within_one_band": round(float(np.mean(np.abs(y - pred) <= 1)), 3),
            "mae_bands": round(float(mean_absolute_error(y, pred)), 3),
            "qwk": round(float(cohen_kappa_score(y, pred, weights="quadratic")), 3)}


def fit_band(a: pd.DataFrame) -> dict:
    a = a[~a["non_analytics"].astype(bool)].reset_index(drop=True)
    X, y, groups = band_frame(a), a["band"].astype(int).to_numpy(), a["desc_group"].to_numpy()
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED).split(X, y, groups))
    Xtr, Xte, ytr, yte = X.iloc[tr], X.iloc[te], y[tr], y[te]

    # tune C with grouped 3-fold CV on the training part only
    best_c, best_mae = 1.0, np.inf
    for C in [0.1, 0.3, 1.0]:
        maes = []
        for itr, iva in GroupKFold(n_splits=3).split(Xtr, ytr, groups[tr]):
            m = Pipeline([("prep", band_preprocessor()), ("clf", OrdinalLogit(C=C))])
            m.fit(Xtr.iloc[itr], ytr[itr])
            maes.append(mean_absolute_error(ytr[iva], m.predict(Xtr.iloc[iva])))
        print(f"  band  C={C:<4} grouped-CV MAE={np.mean(maes):.3f}")
        if np.mean(maes) < best_mae:
            best_c, best_mae = C, float(np.mean(maes))

    candidates = {
        "baseline (majority band)": Pipeline([("prep", band_preprocessor()), ("clf", DummyClassifier())]),
        "experience only (ordinal)": Pipeline([("prep", ColumnTransformer([("num", StandardScaler(), NUM_COLS)])),
                                               ("clf", OrdinalLogit(C=best_c))]),
        "full features (multinomial)": Pipeline([("prep", band_preprocessor()),
                                                 ("clf", LogisticRegression(C=best_c, max_iter=3000))]),
        "full features (ordinal)": Pipeline([("prep", band_preprocessor()), ("clf", OrdinalLogit(C=best_c))]),
    }
    comparison, preds = [], {}
    for cname, m in candidates.items():
        m.fit(Xtr, ytr)
        preds[cname] = m.predict(Xte)
        comparison.append({"model": cname, **_ord_metrics(yte, preds[cname])})
        print(f"  band  {cname:<28} {comparison[-1]}")

    chosen = "full features (ordinal)"
    cm = confusion_matrix(yte, preds[chosen], labels=range(len(BAND_ORDER))).tolist()

    final = Pipeline([("prep", band_preprocessor()), ("clf", OrdinalLogit(C=best_c))]).fit(X, y)
    names = final.named_steps["prep"].get_feature_names_out()
    coef = np.mean([m.coef_[0] for m in final.named_steps["clf"].models_], axis=0)
    terms = pd.DataFrame({"term": names, "coef": coef})
    terms["block"] = terms.term.str.split("__").str[0]
    terms["label"] = terms.term.str.split("__").str[1]
    top = {}
    for block in ["skills", "title", "city", "family", "num"]:
        t = terms[terms.block == block].sort_values("coef")
        top[block] = {"raises_band": t.tail(12)[::-1][["label", "coef"]].round(3).to_dict("records"),
                      "lowers_band": t.head(12)[["label", "coef"]].round(3).to_dict("records")}
    skill_vocab = sorted(final.named_steps["prep"].named_transformers_["skills"].vocabulary_.keys())
    cities = sorted(a.city_primary.value_counts().loc[lambda s: s >= 30].index.tolist())
    joblib.dump({"model": final, "bands": BAND_ORDER}, ART / "band_model.joblib")
    return {"n_train": int(len(tr)), "n_test": int(len(te)), "n_groups": int(len(np.unique(groups))),
            "split": "GroupShuffleSplit on desc_group (duplicate adverts never straddle train/test)",
            "best_C": best_c, "comparison": comparison, "chosen": chosen,
            "confusion_matrix": cm, "bands": BAND_ORDER, "top_terms": top,
            "skill_vocabulary": skill_vocab, "cities": cities}


# ==================================================================== driver
def run(frames: dict | None = None) -> dict:
    print("== Phase 3: models ==")
    ART.mkdir(parents=True, exist_ok=True)
    if frames is None:  # standalone run: read the cleaned CSVs written by phase 1
        frames = {n: pd.read_csv(CLEAN / f"{n}.csv") for n in ["JDS", "SDS", "Analytics"]}
    a = frames["Analytics"].copy()
    if a["skill_tokens"].map(type).eq(list).any():  # in-memory frame from phase 1 holds lists
        a["skill_tokens"] = a["skill_tokens"].apply(lambda t: "|".join(t))
    out = {"jds": fit_binary("JDS", frames["JDS"], JDS_FEATURES),
           "sds": fit_binary("SDS", frames["SDS"], SDS_FEATURES),
           "band": fit_band(a)}
    (ART / "models.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"  saved 3 models + models.json to {ART}")
    return out


if __name__ == "__main__":
    run()
