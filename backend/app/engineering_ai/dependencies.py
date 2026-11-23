"""Dependency hooks for Engineering AI.

Shared auth/access/database are owned by Codex.  They are imported lazily so the
module stays importable and testable in isolation.  Tests override the
functions in this module via ``app.dependency_overrides``.

No model API key is ever read here or sent to the frontend.  Providers read
server-side environment variables only (see ``providers.py`` / ``embeddings.py``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

try:  # shared core
    from app.core.database import get_db as _shared_get_db  # type: ignore
    from app.core.auth import get_current_user as _shared_get_current_user  # type: ignore
    from app.core.access import require_project_member as _shared_require_project_member  # type: ignore
    from app.core.access import require_project_role as _shared_require_project_role  # type: ignore

    _HAS_SHARED_DB = True
except Exception:  # pragma: no cover - fallback for isolated/test runs
    _HAS_SHARED_DB = False
    _shared_get_db = None

    from types import SimpleNamespace

    def _shared_get_current_user() -> Any:  # type: ignore[misc]
        return SimpleNamespace(id="dev-user", role="admin")

    def _shared_require_project_member(project_id: str) -> Any:  # type: ignore[misc]
        return _shared_get_current_user()

    def _shared_require_project_role(project_id: str, allowed: set[str]) -> Any:  # type: ignore[misc]
        return _shared_get_current_user()


def _fallback_session_factory() -> Callable[[], Any]:
    """Lazily build a local SQLite session factory for isolated runs only."""

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from .storage import storage_root

    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / "engineering_ai.sqlite3"
    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    from .models import Base

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


_FALLBACK_FACTORY: Optional[Callable[[], Any]] = None


def get_db() -> Iterator[Any]:
    """Yield a DB session (shared core when available)."""

    if _HAS_SHARED_DB and _shared_get_db is not None:
        yield from _shared_get_db()  # type: ignore[misc]
        return

    global _FALLBACK_FACTORY
    if _FALLBACK_FACTORY is None:
        _FALLBACK_FACTORY = _fallback_session_factory()
    db = _FALLBACK_FACTORY()
    try:
        yield db
    finally:
        db.close()


def get_current_user() -> Any:
    return _shared_get_current_user()


def require_project_member(project_id: str) -> Any:
    return _shared_require_project_member(project_id)


def project_access(project_id: str) -> Any:
    """FastAPI dependency wrapper so tests/integration can override access."""

    return require_project_member(project_id)


def project_editor_access(project_id: str) -> Any:
    return _shared_require_project_role(project_id, {"project_manager", "engineer"})


def current_user_id(user: Any) -> Optional[str]:
    return getattr(user, "id", None)


def get_answer_provider():
    from .providers import provider_from_env

    return provider_from_env()


def storage_dir() -> Path:
    """Private storage root for uploaded source documents."""

    configured = os.getenv("ENGINEERING_AI_STORAGE")
    if configured:
        return Path(configured).expanduser()
    return Path("/tmp/opencode/engineering-ai-storage")
