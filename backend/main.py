"""
IceStream API

Day 1: proved FastAPI runs, with a DB-free /health check.
Day 4: adds the read-only dashboard API (backend/routers/) that powers the
React frontend — metrics, timeseries, incidents, and a live WebSocket feed.
Every number these endpoints return is computed on demand from the same
tables the streaming engine (streaming/, monitoring/) writes to; see
backend/queries.py.

Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import incidents, metrics, ws

app = FastAPI(
    title="IceStream API",
    description="Real-Time E-Commerce Data Quality & Observability Platform",
    version="0.1.0",
)

# Allow the React dashboard (different port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics.router)
app.include_router(incidents.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    """Liveness check. No database access on purpose — see module docstring."""
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"service": "IceStream API", "docs": "/docs"}
