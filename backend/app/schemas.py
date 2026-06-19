from pydantic import BaseModel, Field


class MovieOut(BaseModel):
    movie_id: int
    title: str
    genres: str | None = ""
    score: float | None = None
    reason: str | None = None


class MovieCreate(BaseModel):
    title: str
    genres: str = ""
    user_rating: float | None = Field(default=None, ge=0.5, le=5.0)


class RecommendationResponse(BaseModel):
    model: str
    user_id: int | None = None
    movie_id: int | None = None
    cached: bool = False
    recommendations: list[MovieOut]


class EventIn(BaseModel):
    user_id: int
    movie_id: int
    event_type: str = Field(pattern="^(click|rating|favorite|skip|view)$")
    event_value: float | None = None


class EventOut(BaseModel):
    status: str
    user_id: int
    movie_id: int
    event_type: str


class ClickIn(BaseModel):
    movie_id: int


class ClickOut(BaseModel):
    movie_id: int
    clicks: int


class ClickStatsOut(BaseModel):
    movie_id: int
    title: str
    recommendations_shown: int
    clicks: int
    click_percentage: float
