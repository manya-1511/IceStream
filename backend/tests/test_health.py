"""
Day 1 backend tests: root endpoint, health endpoint, and real
connectivity checks against PostgreSQL and Redis.

These are integration tests — they require the Docker Compose stack
(postgres + redis reachable) to be running, matching the .env config.
Run with: pytest tests/ -v  (from the backend/ directory, inside the
backend container or with the same env vars available).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.redis_client import get_redis_pool
from app.db.session import AsyncSessionLocal
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body == {"service": "IceStream API", "status": "running"}


@pytest.mark.asyncio
async def test_health_endpoint_structure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert set(body["services"].keys()) == {"api", "postgres", "redis"}


@pytest.mark.asyncio
async def test_postgres_connectivity_directly():
    """Verifies the app can actually open a session and run a query —
    not a mocked/fake check."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import text

        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_redis_connectivity_directly():
    client = get_redis_pool()
    pong = await client.ping()
    assert pong is True
