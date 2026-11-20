"""Database dependency shared by the site routers."""

from __future__ import annotations

try:  # shared core
    from app.core.database import get_db as _shared_get_db  # type: ignore
except Exception:  # pragma: no cover - isolated/test runs
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    _engine = create_engine("sqlite:///:memory:", future=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

    def _shared_get_db():
        session = _SessionLocal()
        try:
            yield session
        finally:
            session.close()


def get_db():
    yield from _shared_get_db()
