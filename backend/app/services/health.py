"""
Health-check service.

Performs real connectivity checks against PostgreSQL and Redis — never
returns a hardcoded "healthy" status (see project Rule 3 / Rule 25).
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis_client import get_redis_pool


@dataclass
class ServiceStatus:
    name: str
    status: str
    detail: str | None = None


async def check_postgres(db: AsyncSession) -> ServiceStatus:
    try:
        await db.execute(text("SELECT 1"))
        return ServiceStatus(name="postgres", status="healthy")
    except Exception as exc:  # noqa: BLE001 - surface real error in detail
        return ServiceStatus(name="postgres", status="unhealthy", detail=str(exc))


async def check_redis() -> ServiceStatus:
    try:
        client = get_redis_pool()
        pong = await client.ping()
        if pong:
            return ServiceStatus(name="redis", status="healthy")
        return ServiceStatus(name="redis", status="unhealthy", detail="no PONG received")
    except Exception as exc:  # noqa: BLE001
        return ServiceStatus(name="redis", status="unhealthy", detail=str(exc))
