from fastapi import FastAPI

from app.api import clicks, evaluation, events, metrics, movies, recommend
from app.db.init_db import init_db


app = FastAPI(title="Movie Cloud Recommender API", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "movie-cloud-recommender"}


app.include_router(recommend.router)
app.include_router(movies.router)
app.include_router(clicks.router)
app.include_router(evaluation.router)
app.include_router(events.router)
app.include_router(metrics.router)
