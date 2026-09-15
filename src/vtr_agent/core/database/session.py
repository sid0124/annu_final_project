"""
VTR-Agent: Database Session Management

SQLAlchemy session management with connection pooling and transaction handling.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass

from vtr_agent.core.config import get_settings

# Configure logging
logger = logging.getLogger("vtr_agent.database")

# Create engine with connection pooling and logging
settings = get_settings()

# SQLite specific configuration
if settings.DATABASE_URL.startswith("sqlite://"):
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
    )
else:
    # PostgreSQL or other database
    engine = create_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=QueuePool,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
    )

# Add connection event listeners
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas on connection."""
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Context manager for database transactions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Initialize database with all tables."""
    # Import all models to ensure they are registered
    from vtr_agent.core.database import models

    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)

        # Run Alembic migrations if config exists
        if Path("alembic.ini").exists():
            from alembic.config import Config
            from alembic import command

            alembic_config = Config("alembic.ini")
            command.upgrade(alembic_config, "head")

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
