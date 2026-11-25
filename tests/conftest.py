"""Pytest fixtures providing a cleanly seeded SQLite database and FastAPI TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.services.snapshot_loader import seed_database


@pytest.fixture()
def db_session():
    """Provide a freshly seeded SQLite session for unit tests."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    seed_database(session, force_reset=True)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    """Provide a FastAPI TestClient backed by a freshly seeded SQLite database."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    seed_database(session, force_reset=True)
    session.close()
    with TestClient(app) as test_client:
        yield test_client
