import os
import time

import psutil
from fastapi import APIRouter

from app.recommender.cache import cache_client


router = APIRouter(prefix="/metrics", tags=["metrics"])
STARTED_AT = time.time()


@router.get("/cache")
def cache_metrics():
    return cache_client.stats()


@router.get("/system")
def system_metrics():
    process = psutil.Process(os.getpid())
    return {
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 3),
        "cpu_percent": process.cpu_percent(interval=0.0),
    }
