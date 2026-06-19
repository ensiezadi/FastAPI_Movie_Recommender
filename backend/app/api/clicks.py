from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.recommender.movie_similarity import movie_similarity_service
from app.schemas import ClickIn, ClickOut, ClickStatsOut


router = APIRouter(prefix="/clicks", tags=["clicks"])


def _stats_payload(stat) -> dict:
    percentage = (stat.clicks / stat.recommendations_shown * 100) if stat.recommendations_shown else 0.0
    return {
        "movie_id": stat.movie_id,
        "title": stat.title,
        "recommendations_shown": stat.recommendations_shown,
        "clicks": stat.clicks,
        "click_percentage": round(percentage, 3),
    }


@router.post("", response_model=ClickOut)
def record_click(payload: ClickIn, db: Session = Depends(get_db)):
    stat = movie_similarity_service.record_click(db, payload.movie_id)
    return {"movie_id": stat.movie_id, "clicks": stat.clicks}


@router.get("/{movie_id}", response_model=ClickStatsOut)
def get_click_stats(movie_id: int, db: Session = Depends(get_db)):
    stat = movie_similarity_service.click_stats(db, movie_id)
    return _stats_payload(stat)
