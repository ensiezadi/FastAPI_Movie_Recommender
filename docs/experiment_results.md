# Experiment Results

本文件用于记录最终论文实验表格。

推荐数据设置：

```text
开发验证集：MovieLens 1M
最终实验集：MovieLens 32M
系统压力测试：MovieLens Latest Full
```

## Recommendation Quality

| Method | Precision@10 | Recall@10 | NDCG@10 | HitRate@10 |
| --- | ---: | ---: | ---: | ---: |
| Popular | TBD | TBD | TBD | TBD |
| Item-CF | TBD | TBD | TBD | TBD |
| implicit-ALS | TBD | TBD | TBD | TBD |
| implicit-BPR | TBD | TBD | TBD | TBD |
| Spark-ALS | TBD | TBD | TBD | TBD |
| Hybrid | TBD | TBD | TBD | TBD |

## System Performance

| Scenario | Avg Latency | p95 Latency | Notes |
| --- | ---: | ---: | --- |
| Hybrid without Redis warmup | TBD | TBD | `hey -n 1000 -c 20` |
| Hybrid with Redis hit | TBD | TBD | repeated request |

## Commands

```bash
hey -n 1000 -c 20 'http://127.0.0.1:8000/recommend/hybrid/1?seed_movie_id=1&limit=10'
docker stats
time docker compose --profile training run --rm trainer python train_als.py
time docker compose --profile training run --rm trainer python train_bpr.py
```
