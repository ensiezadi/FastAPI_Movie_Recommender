from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import UserEvent
from app.db.session import get_db
from app.schemas import EventIn, EventOut


router = APIRouter(tags=["events"])


@router.post("/events", response_model=EventOut)
def create_event(payload: EventIn, db: Session = Depends(get_db)):
    event = UserEvent(**payload.model_dump())
    db.add(event)
    db.commit()
    return {"status": "ok", **payload.model_dump()}
