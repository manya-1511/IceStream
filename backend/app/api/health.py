"""Health-check endpoint router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.health import check_postgres, check_redis

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    postgres_status = await check_postgres(db)
    redis_status = await check_redis()

    services = {
        "api": "healthy",
        "postgres": postgres_status.status,
        "redis": redis_status.status,
    }

    overall = "healthy" if all(v == "healthy" for v in services.values()) else "degraded"

    response = {"status": overall, "services": services}

    # Surface error detail for any unhealthy dependency to aid debugging.
    details = {
        s.name: s.detail
        for s in (postgres_status, redis_status)
        if s.detail is not None
    }
    if details:
        response["details"] = details

    return response
