"""
Day 1 test: the API starts and /health responds correctly.

This test does NOT touch the database on purpose (see backend/main.py) so it
can run in CI or on a fresh machine before Postgres is even set up.

Run with (from the backend/ directory, so `import main` works):
    cd backend
    pytest ../tests/test_health.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_expected_body():
    response = client.get("/health")
    assert response.json() == {"status": "healthy"}


def test_root_returns_200():
    response = client.get("/")
    assert response.status_code == 200
