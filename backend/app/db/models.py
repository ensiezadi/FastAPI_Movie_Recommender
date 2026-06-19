from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    gender = Column(String(8))
    age = Column(Integer)
    occupation = Column(Integer)
    zip_code = Column(String(32))


class Movie(Base):
    __tablename__ = "movies"

    movie_id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False, index=True)
    genres = Column(Text, default="")


class MovieLink(Base):
    __tablename__ = "movie_links"

    movie_id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(32), index=True)
    tmdb_id = Column(String(32), index=True)


class MovieTag(Base):
    __tablename__ = "movie_tags"
    __table_args__ = (UniqueConstraint("user_id", "movie_id", "tag", "timestamp", name="uq_movie_tag_event"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True, nullable=False)
    movie_id = Column(Integer, index=True, nullable=False)
    tag = Column(Text, nullable=False)
    timestamp = Column(BigInteger)


class Rating(Base):
    __tablename__ = "ratings"

    user_id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, primary_key=True, index=True)
    rating = Column(Float, nullable=False)
    timestamp = Column(BigInteger)


class RecommendationStat(Base):
    __tablename__ = "recommendation_stats"

    movie_id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False, default="")
    recommendations_shown = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    movie_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    event_value = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class RecommendationCache(Base):
    __tablename__ = "recommendation_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    model_name = Column(String(64), nullable=False, index=True)
    items = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(64), nullable=False)
    dataset_name = Column(String(64), nullable=False)
    precision_at_10 = Column(Float)
    recall_at_10 = Column(Float)
    ndcg_at_10 = Column(Float)
    hitrate_at_10 = Column(Float)
    train_time_seconds = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
