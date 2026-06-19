from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from scipy.sparse import csr_matrix
from sqlalchemy import create_engine


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://recommender:recommender@postgres:5432/movie_recommender",
)
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/models"))


def load_interactions() -> tuple[csr_matrix, dict[int, int], dict[int, int], dict[int, int]]:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    ratings = pd.read_sql("select user_id, movie_id, rating from ratings", engine)
    if ratings.empty:
        raise RuntimeError("No ratings found. Import MovieLens 1M before training.")

    users = sorted(ratings["user_id"].unique())
    movies = sorted(ratings["movie_id"].unique())
    user_to_index = {int(user_id): idx for idx, user_id in enumerate(users)}
    movie_to_index = {int(movie_id): idx for idx, movie_id in enumerate(movies)}
    index_to_movie = {idx: int(movie_id) for movie_id, idx in movie_to_index.items()}

    row = ratings["user_id"].map(user_to_index).to_numpy()
    col = ratings["movie_id"].map(movie_to_index).to_numpy()
    confidence = (ratings["rating"].astype(float) >= 4).astype(float).to_numpy()
    user_items = csr_matrix((confidence, (row, col)), shape=(len(users), len(movies)))
    return user_items, user_to_index, movie_to_index, index_to_movie


def save_bundle(path: Path, model, user_items, user_to_index, index_to_movie) -> None:
    import joblib

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "user_items": user_items,
            "user_to_index": user_to_index,
            "index_to_movie": index_to_movie,
        },
        path,
    )
    print(f"saved {path}")
