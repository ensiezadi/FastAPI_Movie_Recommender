from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.recommender.cache import cache_client
from app.recommender.movie_similarity import movie_similarity_service
from app.recommender.service import service
from app.schemas import RecommendationResponse


router = APIRouter(prefix="/recommend", tags=["recommendations"])


def _limit(limit: int = Query(10, ge=1, le=100)) -> int:
    return limit


@router.get("/popular", response_model=RecommendationResponse)
def recommend_popular(limit: int = Depends(_limit), db: Session = Depends(get_db)):
    key = f"recommend:popular:{limit}"
    cached = cache_client.get_json(key)
    if cached is not None:
        return {"model": "popular", "cached": True, "recommendations": cached}
    items = service.popular(db, limit)
    cache_client.set_json(key, items)
    return {"model": "popular", "cached": False, "recommendations": items}


@router.get("/movie", response_model=RecommendationResponse)
def recommend_by_movie(
    movie_id: int = Query(..., ge=1),
    limit: int = Depends(_limit),
    db: Session = Depends(get_db),
):
    key = f"recommend:movie-cosine:{movie_id}:{limit}"
    cached = cache_client.get_json(key)
    if cached is not None:
        movie_similarity_service.record_shown(db, cached)
        return {"model": "movie-cosine", "movie_id": movie_id, "cached": True, "recommendations": cached}
    items = movie_similarity_service.recommend_by_movie(db, movie_id, limit)
    if items:
        cache_client.set_json(key, items)
        movie_similarity_service.record_shown(db, items)
    return {"model": "movie-cosine", "movie_id": movie_id, "cached": False, "recommendations": items}


@router.get("/similar/{movie_id}", response_model=RecommendationResponse)
def recommend_similar(movie_id: int, limit: int = Depends(_limit), db: Session = Depends(get_db)):
    key = f"recommend:similar:{movie_id}:{limit}"
    cached = cache_client.get_json(key)
    if cached is not None:
        return {"model": "item-cf", "movie_id": movie_id, "cached": True, "recommendations": cached}
    items = service.similar(db, movie_id, limit)
    cache_client.set_json(key, items)
    return {"model": "item-cf", "movie_id": movie_id, "cached": False, "recommendations": items}


@router.get("/user/{user_id}", response_model=RecommendationResponse)
def recommend_user(user_id: int, limit: int = Depends(_limit), db: Session = Depends(get_db)):
    key = f"recommend:user:{user_id}:{limit}"
    cached = cache_client.get_json(key)
    if cached is not None:
        return {"model": "implicit-als", "user_id": user_id, "cached": True, "recommendations": cached}
    items = service.user_cf(db, user_id, limit)
    cache_client.set_json(key, items)
    return {"model": "implicit-als", "user_id": user_id, "cached": False, "recommendations": items}


@router.get("/hybrid/{user_id}", response_model=RecommendationResponse)
def recommend_hybrid(
    user_id: int,
    seed_movie_id: int | None = Query(None, ge=1),
    limit: int = Depends(_limit),
    db: Session = Depends(get_db),
):
    seed_part = seed_movie_id if seed_movie_id is not None else "none"
    key = f"recommend:hybrid:{user_id}:{seed_part}:{limit}"
    cached = cache_client.get_json(key)
    if cached is not None:
        return {"model": "hybrid", "user_id": user_id, "cached": True, "recommendations": cached}
    items = service.hybrid(db, user_id, limit, seed_movie_id=seed_movie_id)
    cache_client.set_json(key, items)
    return {"model": "hybrid", "user_id": user_id, "cached": False, "recommendations": items}
