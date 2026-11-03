"""Run the whole analysis pipeline in order (phases 1 -> 5).

    python run_all.py

Phase 1  cleaning      data/raw/*        -> data/clean/*.csv + cleaning_report.json
Phase 2  statistics    cleaned frames    -> artifacts/stats.json
Phase 3  models        cleaned frames    -> artifacts/*_model.joblib + models.json
Phase 4  profiles      cleaned frames    -> artifacts/profiles.json
Phase 5  insights      the JSON above    -> artifacts/insights.json

You normally don't run this yourself: the Dockerfile runs it during every build.
"""
import time

from pipeline import cleaning, insights, models, profiles, stats_tests


def main():
    t0 = time.time()
    frames = cleaning.run()          # phase 1
    stats_tests.run(frames)          # phase 2
    models.run(frames)               # phase 3
    profiles.run(frames)             # phase 4
    insights.run()                   # phase 5
    print(f"\nAll phases finished in {time.time() - t0:.0f}s.")


if __name__ == "__main__":
    main()
