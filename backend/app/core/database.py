"""Database configuration and session management with SQLite optimizations."""

from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import settings, ensure_directories

# Ensure target directories exist
ensure_directories()

# Engine creation
# For SQLite, check_same_thread=False allows session sharing across FastAPI threadpool
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce SQLite PRAGMAs on EVERY connection:
    - foreign_keys = ON (disabled by default in SQLite)
    - journal_mode = WAL (Write-Ahead Logging for concurrency)
    - busy_timeout = 5000 (5 seconds wait for locks)
    """
    # Only apply to sqlite connections
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for yielding a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
