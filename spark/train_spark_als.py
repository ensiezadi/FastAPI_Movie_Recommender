import json
import time

from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.recommendation import ALS
from pyspark.sql import SparkSession


def main() -> None:
    started = time.time()
    spark = SparkSession.builder.appName("spark-als-ml1m").getOrCreate()
    ratings = spark.read.parquet("/data/parquet/ratings.parquet")
    train, test = ratings.randomSplit([0.8, 0.2], seed=42)
    als = ALS(
        userCol="user_id",
        itemCol="movie_id",
        ratingCol="rating",
        rank=64,
        maxIter=10,
        regParam=0.05,
        coldStartStrategy="drop",
    )
    model = als.fit(train)
    predictions = model.transform(test)
    rmse = RegressionEvaluator(metricName="rmse", labelCol="rating", predictionCol="prediction").evaluate(predictions)
    result = {"model_name": "Spark-ALS", "dataset_name": "ml-1m", "rmse": rmse, "train_time_seconds": time.time() - started}
    model.write().overwrite().save("/models/spark_als")
    spark.sparkContext.parallelize([json.dumps(result)]).saveAsTextFile("/app/results/spark_als_result.json")
    print(json.dumps(result, indent=2))
    spark.stop()


if __name__ == "__main__":
    main()
