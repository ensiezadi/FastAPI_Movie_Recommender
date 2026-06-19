from __future__ import annotations

import math
import os
from collections import defaultdict

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models import Movie, Rating, RecommendationStat


def movie_payload(movie: Movie, score: float | None = None, reason: str | None = None) -> dict:
    return {
        "movie_id": movie.movie_id,
        "title": movie.title,
        "genres": movie.genres or "",
        "score": None if score is None else float(score),
        "reason": reason,
    }


class MovieSimilarityService:
    """Original-repo parity: recommend movies by rating-vector cosine similarity."""

    max_seed_users = int(os.getenv("MOVIE_COSINE_SEED_USERS", "1000"))
    max_candidate_ratings = int(os.getenv("MOVIE_COSINE_CANDIDATE_RATINGS", "60000"))

    def search_movies(self, db: Session, query: str | None = None, limit: int = 50) -> list[dict]:
        q = db.query(Movie)
        if query:
            q = q.filter(Movie.title.ilike(f"%{query}%"))
            starts_with_query = case((Movie.title.ilike(f"{query}%"), 0), else_=1)
            movies = q.order_by(starts_with_query, Movie.title.asc()).limit(limit).all()
        else:
            movies = q.order_by(Movie.title.asc()).limit(limit).all()
        return [movie_payload(movie) for movie in movies]

    def recommend_by_movie(self, db: Session, movie_id: int, limit: int = 4, min_overlap: int = 2) -> list[dict]:
        seed_rows = (
            db.query(Rating.user_id, Rating.rating)
            .filter(Rating.movie_id == movie_id)
            .order_by(Rating.user_id.asc())
            .limit(self.max_seed_users)
            .all()
        )
        if not seed_rows:
            return self._genre_fallback(db, movie_id, limit)

        seed_ratings = {row.user_id: float(row.rating) for row in seed_rows}
        seed_user_ids = list(seed_ratings.keys())
        seed_norm = math.sqrt(sum(rating * rating for rating in seed_ratings.values()))
        candidate_rows = (
            db.query(Rating.user_id, Rating.movie_id, Rating.rating)
            .filter(Rating.user_id.in_(seed_user_ids), Rating.movie_id != movie_id)
            .limit(self.max_candidate_ratings)
            .all()
        )

        dots: defaultdict[int, float] = defaultdict(float)
        norms: defaultdict[int, float] = defaultdict(float)
        overlaps: defaultdict[int, int] = defaultdict(int)
        for row in candidate_rows:
            rating = float(row.rating)
            dots[row.movie_id] += seed_ratings[row.user_id] * rating
            norms[row.movie_id] += rating * rating
            overlaps[row.movie_id] += 1

        scored = []
        for candidate_id, dot in dots.items():
            overlap = overlaps[candidate_id]
            if overlap < min_overlap:
                continue
            denom = seed_norm * math.sqrt(norms[candidate_id])
            if denom:
                scored.append((dot / denom, overlap, candidate_id))
        if not scored:
            return self._genre_fallback(db, movie_id, limit)

        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        top = scored[:limit]
        movie_ids = [candidate_id for _score, _overlap, candidate_id in top]
        movies = {movie.movie_id: movie for movie in db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()}
        return [
            movie_payload(movies[candidate_id], score, f"rating cosine: {overlap} sampled shared users")
            for score, overlap, candidate_id in top
            if candidate_id in movies
        ]

    def record_shown(self, db: Session, items: list[dict]) -> None:
        for item in items:
            movie_id = int(item["movie_id"])
            stat = db.get(RecommendationStat, movie_id)
            if stat is None:
                stat = RecommendationStat(
                    movie_id=movie_id,
                    title=item.get("title") or "",
                    recommendations_shown=0,
                    clicks=0,
                )
                db.add(stat)
            stat.title = item.get("title") or stat.title
            stat.recommendations_shown += 1
        db.commit()

    def record_click(self, db: Session, movie_id: int) -> RecommendationStat:
        movie = db.get(Movie, movie_id)
        stat = db.get(RecommendationStat, movie_id)
        if stat is None:
            stat = RecommendationStat(
                movie_id=movie_id,
                title=movie.title if movie else "",
                recommendations_shown=0,
                clicks=0,
            )
            db.add(stat)
        if movie:
            stat.title = movie.title
        stat.clicks += 1
        db.commit()
        db.refresh(stat)
        return stat

    def click_stats(self, db: Session, movie_id: int) -> RecommendationStat:
        movie = db.get(Movie, movie_id)
        stat = db.get(RecommendationStat, movie_id)
        if stat is None:
            stat = RecommendationStat(
                movie_id=movie_id,
                title=movie.title if movie else "",
                recommendations_shown=0,
                clicks=0,
            )
            db.add(stat)
            db.commit()
            db.refresh(stat)
        return stat

    def add_movie(self, db: Session, title: str, genres: str = "", user_rating: float | None = None) -> Movie:
        existing = db.query(Movie).filter(func.lower(Movie.title) == title.lower()).first()
        if existing is not None:
            return existing

        next_id = (db.query(func.max(Movie.movie_id)).scalar() or 0) + 1
        movie = Movie(movie_id=next_id, title=title, genres=genres)
        db.add(movie)
        if user_rating is not None:
            db.add(Rating(user_id=999999, movie_id=next_id, rating=float(user_rating), timestamp=None))
        db.commit()
        db.refresh(movie)
        return movie

    def _genre_fallback(self, db: Session, movie_id: int, limit: int) -> list[dict]:
        target = db.get(Movie, movie_id)
        if target is None:
            return []
        target_genres = set((target.genres or "").split("|")) - {""}
        if not target_genres:
            return []
        scored = []
        candidates = db.query(Movie).filter(Movie.movie_id != movie_id).limit(5000).all()
        for movie in candidates:
            genres = set((movie.genres or "").split("|")) - {""}
            union = target_genres | genres
            if not union:
                continue
            score = len(target_genres & genres) / len(union)
            if score > 0:
                scored.append((score, movie))
        scored.sort(key=lambda item: (-item[0], item[1].movie_id))
        return [movie_payload(movie, score, "genre cold-start fallback") for score, movie in scored[:limit]]


movie_similarity_service = MovieSimilarityService()
