"""
WS /ws/metrics

Pushes a fresh { summary, point } tick every TICK_SECONDS. There is no
persistent "live" state on the server — each tick just re-runs the same
queries used by the REST endpoints (backend/queries.py) against Postgres,
so a WebSocket client sees exactly the same numbers a REST poll would,
just without the client having to poll itself.

The streaming engine (streaming/, monitoring/) and this API are separate
processes; they only communicate through the database. This endpoint does
not know or care whether a stream is currently running — it just reports
what's actually in the tables right now.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

import queries
from database import engine

router = APIRouter()

TICK_SECONDS = 2
BUCKET_SECONDS = 10


@router.websocket("/ws/metrics")
async def metrics_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            # queries.py uses a synchronous SQLAlchemy engine; running it in
            # a thread keeps this from blocking other requests/connections
            # while Postgres responds.
            summary = await run_in_threadpool(queries.get_summary, engine)
            point = await run_in_threadpool(queries.get_latest_point, engine, BUCKET_SECONDS)
            await websocket.send_json({"summary": summary, "point": point})
            await asyncio.sleep(TICK_SECONDS)
    except WebSocketDisconnect:
        pass
