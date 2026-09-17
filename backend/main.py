"""
IceStream API — Day 1

Today this app only proves that:
  1. FastAPI runs.
  2. It can be imported/started without a database connection (the /health
     endpoint does not touch the DB, so you can verify the API works even
     before Postgres is set up).

Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="IceStream API",
    description="Real-Time E-Commerce Data Quality & Observability Platform",
    version="0.1.0",
)

# Allow the future React dashboard (different port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness check. No database access on purpose — see module docstring."""
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"service": "IceStream API", "docs": "/docs"}
