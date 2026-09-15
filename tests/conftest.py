"""
VTR-Agent: Pytest Configuration & Shared Fixtures

Provides a FastAPI TestClient with a transient in-memory SQLite DB,
seed users (admin / enduser), and pre-authenticated headers.
"""
from __future__ import annotations

import os

# Override config BEFORE importing any vtr_agent modules
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DEMO_MODE", "true")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# -- In-memory test database -------------------------------------------------
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)

# -- App imports (after env vars are set) ------------------------------------
import vtr_agent.core.database.session as _db_session_module
# Patch SessionLocal BEFORE the app is fully imported so get_current_user
# (which does a late import of SessionLocal) picks up the test session.
_db_session_module.SessionLocal = TestingSessionLocal

from vtr_agent.main import app
from vtr_agent.core.database.session import Base, get_db
from vtr_agent.auth.security import get_password_hash


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables and seed demo users once per test session."""
    from vtr_agent.core.database import models  # noqa: F401 - registers ORM models

    Base.metadata.create_all(bind=TEST_ENGINE)

    db = TestingSessionLocal()
    try:
        from vtr_agent.core.database.models import User
        from vtr_agent.utils import new_id

        existing = db.query(User).filter(User.username == "admin").first()
        if existing is None:
            admin = User(
                user_id=new_id("USR"),
                username="admin",
                email="admin@vtr.test",
                full_name="Admin User",
                password_hash=get_password_hash("Demo@12345"),
                role="admin",
                is_active=True,
                is_demo=True,
            )
            enduser = User(
                user_id=new_id("USR"),
                username="enduser",
                email="enduser@vtr.test",
                full_name="End User",
                password_hash=get_password_hash("Demo@12345"),
                role="end_user",
                is_active=True,
                is_demo=True,
            )
            db.add_all([admin, enduser])
            db.commit()
    finally:
        db.close()

    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="session")
def client(setup_database):
    """FastAPI TestClient with test DB dependency override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def auth_headers(client):
    """Bearer token headers for the seeded admin user."""
    r = client.post("/auth/login", json={"username": "admin", "password": "Demo@12345"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
