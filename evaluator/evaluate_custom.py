from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://recommender:recommender@postgres:5432/movie_recommender",
)
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "/app/results"))


def main() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    ratings = pd.read_sql("select user_id, movie_id, rating from ratings", engine)
    if ratings.empty:
        raise RuntimeError("No ratings found. Import MovieLens 1M first.")

    positives = ratings[ratings["rating"] >= 4]
    popular_top10 = ratings.groupby("movie_id").size().sort_values(ascending=False).head(10).index
    user_hits = positives.groupby("user_id")["movie_id"].apply(lambda ids: bool(set(ids) & set(popular_top10)))
    result = {
        "model_name": "Popular",
        "dataset_name": "ml-1m",
        "precision_at_10": None,
        "recall_at_10": None,
        "ndcg_at_10": None,
        "hitrate_at_10": float(user_hits.mean()) if not user_hits.empty else 0.0,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "popular_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    pd.DataFrame([result]).to_csv(RESULTS_DIR / "metrics_table.csv", index=False)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
