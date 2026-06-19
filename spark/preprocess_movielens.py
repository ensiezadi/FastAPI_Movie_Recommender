from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import split


def main() -> None:
    spark = SparkSession.builder.appName("movielens-preprocess").getOrCreate()
    raw_32m = "/data/raw/ml-32m"
    raw_1m = "/data/raw/ml-1m"
    out = "/data/parquet"

    if Path(f"{raw_32m}/ratings.csv").exists() and Path(f"{raw_32m}/movies.csv").exists():
        ratings = spark.read.option("header", True).csv(f"{raw_32m}/ratings.csv")
        movies = spark.read.option("header", True).csv(f"{raw_32m}/movies.csv")
        ratings = ratings.selectExpr(
            "cast(userId as int) as user_id",
            "cast(movieId as int) as movie_id",
            "cast(rating as float) as rating",
            "cast(timestamp as long) as timestamp",
        )
        movies = movies.selectExpr("cast(movieId as int) as movie_id", "title", "genres")
    else:
        ratings = spark.read.text(f"{raw_1m}/ratings.dat").select(split("value", "::").alias("p"))
        ratings = ratings.selectExpr(
            "cast(p[0] as int) as user_id",
            "cast(p[1] as int) as movie_id",
            "cast(p[2] as float) as rating",
            "cast(p[3] as long) as timestamp",
        )
        movies = spark.read.text(f"{raw_1m}/movies.dat").select(split("value", "::").alias("p"))
        movies = movies.selectExpr("cast(p[0] as int) as movie_id", "p[1] as title", "p[2] as genres")

    ratings.write.mode("overwrite").parquet(f"{out}/ratings.parquet")
    movies.write.mode("overwrite").parquet(f"{out}/movies.parquet")
    spark.stop()


if __name__ == "__main__":
    main()
