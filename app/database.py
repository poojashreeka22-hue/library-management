"""
Library Management System - Database configuration and session management.

Provides the SQLAlchemy engine, session factory, declarative base, and a
FastAPI dependency that yields a database session per request.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------
Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db():
    """Yield a database session and ensure it is closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Table initialisation
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Import all models and create any missing tables.

    Call this once at application startup (e.g. in a lifespan handler).
    """
    import os
    from sqlalchemy import text

    # Ensure uploads directory exists
    uploads_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Import models so that Base.metadata is populated before create_all.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Backward-compatible column migration for books.cover_image if not present
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE books ADD COLUMN cover_image VARCHAR(500)"))
            conn.commit()
    except Exception:
        pass  # Column already exists or table is fresh
