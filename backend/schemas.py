"""Response models for the dashboard API. Keeps routers thin and gives the
auto-generated docs (/docs) accurate shapes for the frontend to code against."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

PipelineStatus = Literal["HEALTHY", "DEGRADED", "QUARANTINED", "RECOVERING"]


class MetricsSummary(BaseModel):
    events_per_sec: float
    total_processed: int
    quality_score: float
    error_rate: float
    quarantined_count: int
    active_incidents: int
    status: PipelineStatus


class TimeseriesPoint(BaseModel):
    timestamp: str
    events_per_sec: float
    quality_score: Optional[float] = None


class TimeseriesResponse(BaseModel):
    points: list[TimeseriesPoint]


class Incident(BaseModel):
    incident_id: int
    started_at: str
    resolved_at: Optional[str] = None
    type: Literal["ERROR_RATE", "VOLUME"]
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    error_rate: Optional[float] = None
    description: str
    status: Literal["ACTIVE", "RECOVERING", "RESOLVED"]
    affected_field: Optional[str] = None


class WebSocketTick(BaseModel):
    summary: MetricsSummary
    point: TimeseriesPoint
