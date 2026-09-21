"""
GET /api/metrics/summary     - current pipeline metrics, for the metric cards
GET /api/metrics/timeseries  - bucketed history, for the two line charts
"""

from __future__ import annotations

from fastapi import APIRouter, Query

import queries
from database import engine
from schemas import MetricsSummary, TimeseriesResponse

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummary)
def summary() -> dict:
    return queries.get_summary(engine)


@router.get("/timeseries", response_model=TimeseriesResponse)
def timeseries(
    window_minutes: int = Query(5, ge=1, le=60, description="How far back to look"),
    bucket_seconds: int = Query(10, ge=1, le=300, description="Width of each point"),
) -> dict:
    # Cap the number of buckets so the response (and the chart) stay small
    # regardless of what window/bucket combination is requested. generate_series
    # is inclusive of both endpoints (count = window/bucket + 1), so bucket_seconds
    # is chosen to keep that inclusive count at or under max_points.
    max_points = 300
    window_seconds = window_minutes * 60
    if window_seconds / bucket_seconds >= max_points:
        bucket_seconds = window_seconds // max_points + 1

    points = queries.get_timeseries(engine, window_minutes, bucket_seconds)
    return {"points": points}
