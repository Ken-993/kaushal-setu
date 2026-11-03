from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
ART = ROOT / "artifacts"

SEED = 42

# Salary bands in ascending order (ordinal target for Analytics Jobs)
BAND_ORDER = ["0to3", "3to6", "6to10", "10to15", "15to25", "25to50"]
BAND_MAP = {b: i for i, b in enumerate(BAND_ORDER)}

JDS_FEATURES = [
    "big_data_skills", "maths_stats_skills", "coding_skills",
    "ai_and_ml_skills", "dashboard_and_storytelling_skills",
]
SDS_FEATURES = [
    "neuroticism", "extraversion", "openness_to_experience",
    "agreeableness", "conscientiousness",
]

# Keyword taxonomy: market skill text -> the five internal competency families.
# (Documented judgement; swap for an embedding / zero-shot mapper later.)
TAXONOMY = {
    "big_data": ["big data", "hadoop", "spark", "hive", "kafka", "pyspark", "hdfs", "mapreduce", "nosql", "data lake"],
    "maths_stats": ["statistic", "sas", "regression", "forecast", "predictive", "econometric", "probability", "r programming", "matlab"],
    "coding": ["python", "sql", "java", "c++", "scala", "javascript", "coding", "programming", "pl/sql", "plsql"],
    "ai_ml": ["machine learning", "deep learning", "nlp", "tensorflow", "pytorch", "neural", "artificial intelligence", "computer vision", "ai"],
    "dashboards": ["tableau", "power bi", "powerbi", "dashboard", "visuali", "qlik", "reporting", "storytelling", "looker"],
}
