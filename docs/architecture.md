# Architecture

本系统采用在线服务、离线训练、离线评估三层解耦。

在线链路：

```text
Streamlit -> FastAPI -> Redis cache -> PostgreSQL -> recommender service -> Redis cache -> response
```

离线训练链路：

```text
MovieLens 1M/32M/latest -> PostgreSQL -> trainer -> models/*.joblib -> FastAPI load on demand
```

离线实验链路：

```text
MovieLens 1M/32M/latest -> RecBole / Spark MLlib -> evaluator/results
```

数据库核心表：

```text
users(user_id, gender, age, occupation, zip_code)
movies(movie_id, title, genres)
ratings(user_id, movie_id, rating, timestamp)
user_events(id, user_id, movie_id, event_type, event_value, created_at)
recommendation_cache(id, user_id, model_name, items, created_at)
experiment_results(id, model_name, dataset_name, metrics, created_at)
```
