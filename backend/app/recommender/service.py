from __future__ import annotations

import math
import os
from collections import Counter, defaultdict
from pathlib import Path

import joblib
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import Movie, Rating, UserEvent


MODEL_DIR = Path(os.getenv("MODEL_DIR", "/models"))
MAX_ITEM_CF_SEED_USERS = int(os.getenv("MAX_ITEM_CF_SEED_USERS", "800"))
MAX_ITEM_CF_RATINGS = int(os.getenv("MAX_ITEM_CF_RATINGS", "20000"))
MAX_USER_CF_PEERS = int(os.getenv("MAX_USER_CF_PEERS", "300"))
MAX_USER_CF_RATINGS = int(os.getenv("MAX_USER_CF_RATINGS", "3000"))


def _movie_dict(movie: Movie, score: float | None = None, reason: str | None = None) -> dict:
    return {
        "movie_id": movie.movie_id,
        "title": movie.title,
        "genres": movie.genres or "",
        "score": None if score is None else float(score),
        "reason": reason,
    }


class RecommendationService:
    def popular(self, db: Session, limit: int = 10) -> list[dict]:
        rows = (
            db.query(
                Movie,
                func.count(Rating.user_id).label("rating_count"),
                func.avg(Rating.rating).label("avg_rating"),
            )
            .join(Rating, Rating.movie_id == Movie.movie_id)
            .group_by(Movie.movie_id)
            .order_by(desc("rating_count"), desc("avg_rating"))
            .limit(limit)
            .all()
        )
        return [
            _movie_dict(movie, float(avg_rating or 0), f"popular: {rating_count} ratings")
            for movie, rating_count, avg_rating in rows
        ]

    def similar(self, db: Session, movie_id: int, limit: int = 10) -> list[dict]:
        cf_items = self._item_cf_from_seed(db, movie_id, limit)
        if cf_items:
            return cf_items

        return self._genre_similar(db, movie_id, limit)

    def _genre_similar(self, db: Session, movie_id: int, limit: int = 10) -> list[dict]:
        target = db.get(Movie, movie_id)
        if target is None:
            return []

        target_genres = set((target.genres or "").split("|")) - {""}
        if not target_genres:
            return self.popular(db, limit)

        candidates = db.query(Movie).filter(Movie.movie_id != movie_id).all()
        scored = []
        for movie in candidates:
            genres = set((movie.genres or "").split("|")) - {""}
            union = target_genres | genres
            score = len(target_genres & genres) / len(union) if union else 0.0
            if score > 0:
                scored.append((score, movie))
        scored.sort(key=lambda item: (-item[0], item[1].movie_id))
        return [_movie_dict(movie, score, "genre fallback") for score, movie in scored[:limit]]

    def user_cf(self, db: Session, user_id: int, limit: int = 10) -> list[dict]:
        model_result = self._implicit_recommend(db, user_id, limit)
        if model_result:
            return model_result
        return self._cooccurrence_recommend(db, user_id, limit) or self.popular(db, limit)

    def hybrid(self, db: Session, user_id: int, limit: int = 10, seed_movie_id: int | None = None) -> list[dict]:
        cf = self._implicit_recommend(db, user_id, max(limit * 3, 20))
        if not cf:
            cf = self._user_genre_profile(db, user_id, max(limit * 3, 20))
        item_cf = self._item_cf_from_seed(db, seed_movie_id, max(limit * 3, 20)) if seed_movie_id is not None else []
        popular = [] if (cf or item_cf) else self.popular(db, max(limit * 3, 20))

        rated_movie_ids = {
            row.movie_id for row in db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
        }
        recent_movie_ids = [
            row.movie_id
            for row in (
                db.query(UserEvent.movie_id)
                .filter(UserEvent.user_id == user_id)
                .order_by(UserEvent.created_at.desc())
                .limit(10)
                .all()
            )
        ]
        if seed_movie_id is not None:
            recent_movie_ids = [seed_movie_id, *[movie_id for movie_id in recent_movie_ids if movie_id != seed_movie_id]]

        content_scores: dict[int, float] = defaultdict(float)
        for movie_id in recent_movie_ids[:3]:
            for item in self._genre_similar(db, movie_id, limit=20):
                content_scores[item["movie_id"]] = max(content_scores[item["movie_id"]], item["score"] or 0)

        score_map: dict[int, float] = defaultdict(float)
        item_map: dict[int, dict] = {}

        has_seed_signal = bool(item_cf)
        user_weight = 0.25 if has_seed_signal else 0.60
        item_weight = 0.60 if has_seed_signal else 0.0
        content_weight = 0.05 if has_seed_signal else 0.20
        popularity_weight = 0.10

        for rank, item in enumerate(cf):
            score_map[item["movie_id"]] += user_weight * (1.0 / (rank + 1))
            item["reason"] = self._merge_reason(item.get("reason"), "user-cf")
            item_map[item["movie_id"]] = item
        for rank, item in enumerate(item_cf):
            score_map[item["movie_id"]] += item_weight * (1.0 / (rank + 1))
            item["reason"] = self._merge_reason(item.get("reason"), "seed-item-cf")
            item_map[item["movie_id"]] = item
        for rank, item in enumerate(popular):
            score_map[item["movie_id"]] += popularity_weight * (1.0 / (rank + 1))
            item["reason"] = self._merge_reason(item.get("reason"), "popular")
            item_map[item["movie_id"]] = item
        for movie_id, score in content_scores.items():
            score_map[movie_id] += content_weight * score
        for movie_id in recent_movie_ids:
            score_map[movie_id] += 0.10

        if not item_map:
            return []
        missing_ids = [movie_id for movie_id in score_map if movie_id not in item_map]
        if missing_ids:
            for movie in db.query(Movie).filter(Movie.movie_id.in_(missing_ids)).all():
                reason = "content genre" if movie.movie_id in content_scores else None
                item_map[movie.movie_id] = _movie_dict(movie, reason=reason)

        ranked = [
            (score, item_map[movie_id])
            for movie_id, score in score_map.items()
            if movie_id not in rated_movie_ids and movie_id in item_map
        ]
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["movie_id"]))
        return [
            {**item, "score": round(score, 6), "reason": item.get("reason") or "hybrid"}
            for score, item in ranked[:limit]
        ]

    def _item_cf_from_seed(self, db: Session, movie_id: int | None, limit: int) -> list[dict]:
        if movie_id is None:
            return []

        seed_likers = (
            db.query(Rating.user_id)
            .filter(Rating.movie_id == movie_id, Rating.rating >= 4)
            .limit(MAX_ITEM_CF_SEED_USERS)
            .all()
        )
        liker_ids = [row.user_id for row in seed_likers]
        if not liker_ids:
            return []

        co_ratings = (
            db.query(Rating.movie_id, Rating.rating)
            .filter(
                Rating.user_id.in_(liker_ids),
                Rating.rating >= 4,
                Rating.movie_id != movie_id,
            )
            .limit(MAX_ITEM_CF_RATINGS)
            .all()
        )
        if not co_ratings:
            return []

        counts: Counter[int] = Counter()
        rating_sums: defaultdict[int, float] = defaultdict(float)
        for row in co_ratings:
            counts[row.movie_id] += 1
            rating_sums[row.movie_id] += float(row.rating)

        top_movie_ids = [movie_id for movie_id, _count in counts.most_common(limit)]
        movies = {
            movie.movie_id: movie
            for movie in db.query(Movie).filter(Movie.movie_id.in_(top_movie_ids)).all()
        }
        max_count = max(counts.values()) or 1
        return [
            _movie_dict(
                movies[candidate_id],
                (count / max_count) * 0.8 + ((rating_sums[candidate_id] / count) / 5.0) * 0.2,
                f"item-cf: {count} sampled users also liked seed",
            )
            for candidate_id, count in counts.most_common(limit)
            if candidate_id in movies
        ]

    def _user_genre_profile(self, db: Session, user_id: int, limit: int) -> list[dict]:
        liked_movies = (
            db.query(Movie)
            .join(Rating, Rating.movie_id == Movie.movie_id)
            .filter(Rating.user_id == user_id, Rating.rating >= 4)
            .limit(30)
            .all()
        )
        if not liked_movies:
            return []

        genre_counts: Counter[str] = Counter()
        for movie in liked_movies:
            genre_counts.update(genre for genre in (movie.genres or "").split("|") if genre)
        if not genre_counts:
            return []

        seen_movie_ids = {row.movie_id for row in db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()}
        candidates = db.query(Movie).limit(5000).all()
        scored = []
        max_genre_hits = max(genre_counts.values()) or 1
        for movie in candidates:
            if movie.movie_id in seen_movie_ids:
                continue
            genres = [genre for genre in (movie.genres or "").split("|") if genre]
            if not genres:
                continue
            score = sum(genre_counts.get(genre, 0) for genre in genres) / (len(genres) * max_genre_hits)
            if score > 0:
                scored.append((score, movie))
        scored.sort(key=lambda item: (-item[0], item[1].movie_id))
        return [_movie_dict(movie, score, "user genre profile") for score, movie in scored[:limit]]

    def _cooccurrence_recommend(self, db: Session, user_id: int, limit: int) -> list[dict]:
        liked = [
            row.movie_id
            for row in (
                db.query(Rating.movie_id)
                .filter(Rating.user_id == user_id, Rating.rating >= 4)
                .limit(20)
                .all()
            )
        ]
        if not liked:
            return []

        peer_users = (
            db.query(Rating.user_id)
            .filter(Rating.movie_id.in_(liked), Rating.rating >= 4, Rating.user_id != user_id)
            .limit(MAX_USER_CF_PEERS)
            .all()
        )
        peer_ids = [row.user_id for row in peer_users]
        if not peer_ids:
            return []

        user_seen = {row.movie_id for row in db.query(Rating.movie_id).filter(Rating.user_id == user_id)}
        counts = Counter(
            row.movie_id
            for row in (
                db.query(Rating.movie_id)
                .filter(Rating.user_id.in_(peer_ids), Rating.rating >= 4)
                .limit(MAX_USER_CF_RATINGS)
                .all()
            )
            if row.movie_id not in user_seen
        )
        if not counts:
            return []

        movies = {
            movie.movie_id: movie
            for movie in db.query(Movie).filter(Movie.movie_id.in_(list(counts.keys()))).all()
        }
        return [
            _movie_dict(movies[movie_id], math.log(count + 1), "cooccurrence fallback")
            for movie_id, count in counts.most_common(limit)
            if movie_id in movies
        ]

    def _merge_reason(self, current: str | None, label: str) -> str:
        if not current:
            return label
        if label in current:
            return current
        return f"{current}; {label}"

    def _implicit_recommend(self, db: Session, user_id: int, limit: int) -> list[dict]:
        bundle_path = MODEL_DIR / "implicit_als.joblib"
        if not bundle_path.exists():
            return []
        try:
            bundle = joblib.load(bundle_path)
            model = bundle["model"]
            user_items = bundle["user_items"]
            user_to_index = bundle["user_to_index"]
            index_to_movie = bundle["index_to_movie"]
        except Exception:
            return []
        if user_id not in user_to_index:
            return []

        try:
            ids, scores = model.recommend(
                user_to_index[user_id],
                user_items[user_to_index[user_id]],
                N=limit,
                filter_already_liked_items=True,
            )
        except Exception:
            return []

        movie_ids = [int(index_to_movie[int(idx)]) for idx in ids]
        movies = {
            movie.movie_id: movie
            for movie in db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()
        }
        return [
            _movie_dict(movies[movie_id], float(score), "implicit als")
            for movie_id, score in zip(movie_ids, scores)
            if movie_id in movies
        ]


service = RecommendationService()
