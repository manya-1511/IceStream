"""GET /api/incidents - recent incidents, for the incident panel."""

from __future__ import annotations

from fastapi import APIRouter, Query

import queries
from database import engine
from schemas import Incident

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[Incident])
def list_incidents(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    return queries.get_incidents(engine, limit=limit)
