from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.recommender.movie_similarity import movie_similarity_service
from app.schemas import MovieCreate, MovieOut


router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("", response_model=list[MovieOut])
def list_movies(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return movie_similarity_service.search_movies(db, query=None, limit=limit)


@router.get("/search", response_model=list[MovieOut])
def search_movies(
    q: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return movie_similarity_service.search_movies(db, query=q or None, limit=limit)


@router.post("", response_model=MovieOut)
def create_movie(payload: MovieCreate, db: Session = Depends(get_db)):
    movie = movie_similarity_service.add_movie(
        db,
        title=payload.title,
        genres=payload.genres,
        user_rating=payload.user_rating,
    )
    return {"movie_id": movie.movie_id, "title": movie.title, "genres": movie.genres or ""}
