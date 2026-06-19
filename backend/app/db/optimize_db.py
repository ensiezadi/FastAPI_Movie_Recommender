from sqlalchemy import text

from app.db.session import engine


INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_ratings_movie_rating ON ratings (movie_id, rating)",
    "CREATE INDEX IF NOT EXISTS idx_ratings_user_rating ON ratings (user_id, rating)",
    "CREATE INDEX IF NOT EXISTS idx_ratings_movie_user ON ratings (movie_id, user_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_user_created ON user_events (user_id, created_at DESC)",
]


def optimize_db() -> None:
    with engine.begin() as conn:
        for statement in INDEX_STATEMENTS:
            print(statement)
            conn.execute(text(statement))
    print("database optimization indexes are ready")


if __name__ == "__main__":
    optimize_db()
