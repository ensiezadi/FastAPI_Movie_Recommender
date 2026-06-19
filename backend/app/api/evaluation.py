from __future__ import annotations

import math
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Movie, Rating, User
from app.db.session import get_db
from app.recommender.movie_similarity import movie_similarity_service


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/summary")
def evaluation_summary(
    sample_size: int = Query(20, ge=1, le=100),
    k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Run a lightweight sampled leave-one-out evaluation for the movie-similarity demo."""
    candidate_users = (
        db.query(User.user_id)
        .order_by(User.user_id.asc())
        .limit(sample_size * 20)
        .all()
    )

    cases = []
    timings = []
    hits = []
    precisions = []
    recalls = []
    ndcgs = []

    for user_row in candidate_users:
        if len(cases) >= sample_size:
            break
        positives = (
            db.query(Rating.movie_id)
            .filter(Rating.user_id == user_row.user_id, Rating.rating >= 4)
            .order_by(Rating.timestamp.asc())
            .limit(50)
            .all()
        )
        movie_ids = [row.movie_id for row in positives]
        if len(movie_ids) < 2:
            continue

        seed_movie_id = movie_ids[0]
        target_movie_id = movie_ids[-1]
        if seed_movie_id == target_movie_id:
            continue

        started = time.perf_counter()
        recommendations = movie_similarity_service.recommend_by_movie(db, seed_movie_id, k)
        elapsed_ms = (time.perf_counter() - started) * 1000
        timings.append(elapsed_ms)

        recommended_ids = [item["movie_id"] for item in recommendations]
        hit_rank = recommended_ids.index(target_movie_id) + 1 if target_movie_id in recommended_ids else None
        hit = hit_rank is not None
        hits.append(1.0 if hit else 0.0)
        precisions.append((1.0 / k) if hit else 0.0)
        recalls.append(1.0 if hit else 0.0)
        ndcgs.append((1.0 / math.log2(hit_rank + 1)) if hit_rank else 0.0)
        cases.append(
            {
                "user_id": user_row.user_id,
                "seed_movie_id": seed_movie_id,
                "target_movie_id": target_movie_id,
                "hit_rank": hit_rank,
                "latency_ms": round(elapsed_ms, 3),
            }
        )

    def avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 6) if values else 0.0

    sorted_timings = sorted(timings)
    p95_index = max(0, math.ceil(len(sorted_timings) * 0.95) - 1) if sorted_timings else 0

    return {
        "evaluation_type": "sampled_leave_one_out",
        "model_name": "movie-cosine",
        "sample_size_requested": sample_size,
        "sample_size_evaluated": len(cases),
        "k": k,
        "precision_at_k": avg(precisions),
        "recall_at_k": avg(recalls),
        "ndcg_at_k": avg(ndcgs),
        "hitrate_at_k": avg(hits),
        "avg_latency_ms": round(avg(timings), 3),
        "p95_latency_ms": round(sorted_timings[p95_index], 3) if sorted_timings else 0.0,
        "dataset": {
            "users": db.query(func.count(User.user_id)).scalar() or 0,
            "movies": db.query(func.count(Movie.movie_id)).scalar() or 0,
            "ratings": db.query(func.count(Rating.user_id)).scalar() or 0,
        },
        "cases": cases[:10],
        "note": "Sampled demo evaluation: one liked movie is used as the query seed and another liked movie is held out as the target.",
    }
