"""Shared fixtures for organisational-layer integration tests.

Tests run against the real MySQL database configured in .env.
Read-only tests use the data seeded by migrate.py / migrate_rules.py.
Write tests create temporary records with a TEST- prefix and clean up after.
"""

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient using the real database."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    """Yield a real database session and close it afterwards."""
    gen = get_db()
    session = next(gen)
    try:
        yield session
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
