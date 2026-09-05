"""SQLite engine + session helpers.

The vault markdown is the source of truth for document *content*; this database
holds state, relations and workflow. `init_db()` is idempotent - it creates the
file and any missing tables, and is safe to call on every process start.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  - import registers the tables on SQLModel.metadata
from app.config import settings

_DB_URL = f"sqlite:///{settings.db_path}"

engine = create_engine(_DB_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create the database file and any missing tables. Safe to re-run."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Script-side transactional block: commits on success, rolls back on error."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
