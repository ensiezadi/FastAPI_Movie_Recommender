from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from app.db.init_db import init_db
from app.db.models import Movie, MovieLink, MovieTag, Rating, User
from app.db.session import SessionLocal


def _read_dat(path: Path) -> list[list[str]]:
    with path.open("r", encoding="latin-1") as fh:
        return [line.rstrip("\n").split("::") for line in fh if line.strip()]


def _insert_users(db, users: list[dict]) -> None:
    if users:
        db.execute(insert(User).values(users).on_conflict_do_nothing(index_elements=["user_id"]))


def _insert_movies(db, movies: list[dict]) -> None:
    if movies:
        db.execute(insert(Movie).values(movies).on_conflict_do_nothing(index_elements=["movie_id"]))


def _insert_ratings(db, ratings: list[dict]) -> None:
    if ratings:
        db.execute(
            insert(Rating)
            .values(ratings)
            .on_conflict_do_nothing(index_elements=["user_id", "movie_id"])
        )


def _insert_links(db, links: list[dict]) -> None:
    if links:
        db.execute(insert(MovieLink).values(links).on_conflict_do_nothing(index_elements=["movie_id"]))


def _insert_tags(db, tags: list[dict]) -> None:
    if tags:
        db.execute(
            insert(MovieTag)
            .values(tags)
            .on_conflict_do_nothing(
                constraint="uq_movie_tag_event",
            )
        )


def _print_counts(db) -> None:
    print("users", db.query(User).count())
    print("movies", db.query(Movie).count())
    print("ratings", db.query(Rating).count())
    print("links", db.query(MovieLink).count())
    print("tags", db.query(MovieTag).count())


def import_movielens_1m(data_dir: Path, batch_size: int = 10000) -> None:
    users_path = data_dir / "users.dat"
    movies_path = data_dir / "movies.dat"
    ratings_path = data_dir / "ratings.dat"
    missing = [str(path) for path in (users_path, movies_path, ratings_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing MovieLens 1M files: " + ", ".join(missing))

    init_db()
    with SessionLocal() as db:
        users = [
            {
                "user_id": int(user_id),
                "gender": gender,
                "age": int(age),
                "occupation": int(occupation),
                "zip_code": zip_code,
            }
            for user_id, gender, age, occupation, zip_code in _read_dat(users_path)
        ]
        movies = [
            {"movie_id": int(movie_id), "title": title, "genres": genres}
            for movie_id, title, genres in _read_dat(movies_path)
        ]

        _insert_users(db, users)
        _insert_movies(db, movies)
        db.commit()

        batch = []
        for user_id, movie_id, rating, timestamp in _read_dat(ratings_path):
            batch.append(
                {
                    "user_id": int(user_id),
                    "movie_id": int(movie_id),
                    "rating": float(rating),
                    "timestamp": int(timestamp),
                }
            )
            if len(batch) >= batch_size:
                _insert_ratings(db, batch)
                db.commit()
                batch.clear()
        if batch:
            _insert_ratings(db, batch)
            db.commit()

        _print_counts(db)


def import_movielens_csv(data_dir: Path, batch_size: int = 100000, include_tags: bool = True) -> None:
    """Import modern MovieLens CSV datasets, including MovieLens 32M/latest.

    Expected files:
      movies.csv: movieId,title,genres
      ratings.csv: userId,movieId,rating,timestamp
      links.csv: movieId,imdbId,tmdbId       optional
      tags.csv: userId,movieId,tag,timestamp optional

    Modern CSV datasets do not include user demographic columns, so users are
    derived from distinct userId values in ratings.csv. Genome files are not
    imported here because they are large and not needed for the online demo path.
    """
    movies_path = data_dir / "movies.csv"
    ratings_path = data_dir / "ratings.csv"
    links_path = data_dir / "links.csv"
    tags_path = data_dir / "tags.csv"
    missing = [str(path) for path in (movies_path, ratings_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing MovieLens CSV files: " + ", ".join(missing))

    init_db()
    with SessionLocal() as db:
        movies_df = pd.read_csv(movies_path)
        movies = [
            {
                "movie_id": int(row.movieId),
                "title": str(row.title),
                "genres": "" if pd.isna(row.genres) else str(row.genres),
            }
            for row in movies_df.itertuples(index=False)
        ]
        _insert_movies(db, movies)
        db.commit()

        if links_path.exists():
            links_df = pd.read_csv(links_path)
            links = [
                {
                    "movie_id": int(row.movieId),
                    "imdb_id": None if pd.isna(row.imdbId) else str(row.imdbId),
                    "tmdb_id": None if pd.isna(row.tmdbId) else str(int(row.tmdbId)) if isinstance(row.tmdbId, float) else str(row.tmdbId),
                }
                for row in links_df.itertuples(index=False)
            ]
            _insert_links(db, links)
            db.commit()

        seen_users: set[int] = set()
        total = 0
        for chunk in pd.read_csv(ratings_path, chunksize=batch_size):
            chunk = chunk.rename(
                columns={
                    "userId": "user_id",
                    "movieId": "movie_id",
                }
            )
            seen_users.update(int(user_id) for user_id in chunk["user_id"].unique())
            ratings = [
                {
                    "user_id": int(row.user_id),
                    "movie_id": int(row.movie_id),
                    "rating": float(row.rating),
                    "timestamp": int(row.timestamp),
                }
                for row in chunk.itertuples(index=False)
            ]
            _insert_ratings(db, ratings)
            db.commit()
            total += len(ratings)
            print(f"imported_ratings {total}")

        users = [
            {
                "user_id": user_id,
                "gender": None,
                "age": None,
                "occupation": None,
                "zip_code": None,
            }
            for user_id in sorted(seen_users)
        ]
        for start in range(0, len(users), batch_size):
            _insert_users(db, users[start : start + batch_size])
            db.commit()

        if include_tags and tags_path.exists():
            total_tags = 0
            for chunk in pd.read_csv(tags_path, chunksize=batch_size):
                chunk = chunk.rename(columns={"userId": "user_id", "movieId": "movie_id"})
                tags = [
                    {
                        "user_id": int(row.user_id),
                        "movie_id": int(row.movie_id),
                        "tag": "" if pd.isna(row.tag) else str(row.tag),
                        "timestamp": int(row.timestamp),
                    }
                    for row in chunk.itertuples(index=False)
                    if not pd.isna(row.tag)
                ]
                _insert_tags(db, tags)
                db.commit()
                total_tags += len(tags)
                print(f"imported_tags {total_tags}")

        _print_counts(db)


def detect_dataset(data_dir: Path) -> str:
    if (data_dir / "users.dat").exists() and (data_dir / "movies.dat").exists() and (data_dir / "ratings.dat").exists():
        return "1m"
    if (data_dir / "movies.csv").exists() and (data_dir / "ratings.csv").exists():
        return "csv"
    raise FileNotFoundError(
        "Could not detect MovieLens format. Expected users.dat/movies.dat/ratings.dat "
        "or movies.csv/ratings.csv."
    )


def import_movielens(
    data_dir: Path,
    dataset: str = "auto",
    batch_size: int | None = None,
    include_tags: bool = True,
) -> None:
    selected = detect_dataset(data_dir) if dataset == "auto" else dataset
    if selected == "1m":
        import_movielens_1m(data_dir, batch_size=batch_size or 10000)
    elif selected in {"csv", "32m", "latest"}:
        import_movielens_csv(data_dir, batch_size=batch_size or 100000, include_tags=include_tags)
    else:
        raise ValueError("dataset must be one of: auto, 1m, csv, 32m, latest")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MovieLens 1M or modern CSV MovieLens datasets into PostgreSQL.")
    parser.add_argument("--data-dir", default="/data/raw/ml-1m", help="MovieLens dataset directory")
    parser.add_argument("--dataset", default="auto", choices=["auto", "1m", "csv", "32m", "latest"])
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--skip-tags", action="store_true", help="Skip optional tags.csv import for large latest/full datasets")
    args = parser.parse_args()
    import_movielens(
        Path(args.data_dir),
        dataset=args.dataset,
        batch_size=args.batch_size,
        include_tags=not args.skip_tags,
    )


if __name__ == "__main__":
    main()
