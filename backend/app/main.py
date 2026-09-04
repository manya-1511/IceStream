"""
IceStream API — FastAPI application entrypoint.

Day 1 scope: application bootstrap, health checks, and CORS only.
Business routers are added in later days under app/api/.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened once the frontend origin is finalized
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)


@app.get("/")
async def root() -> dict:
    return {"service": "IceStream API", "status": "running"}
