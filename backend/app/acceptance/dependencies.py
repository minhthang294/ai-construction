"""Dependency hooks for the Acceptance module.

Shared auth/access is owned by Codex.  We import it lazily so the module can be
mounted in the real app or exercised in isolation with dependency overrides.
"""

from __future__ import annotations

from typing import Any, Optional

try:  # shared core
    from app.core.auth import get_current_user as _shared_get_current_user  # type: ignore
    from app.core.access import require_project_member as _shared_require_project_member  # type: ignore
    from app.core.access import require_project_role as _shared_require_project_role  # type: ignore
except Exception:  # pragma: no cover - fallback for isolated/test runs
    from types import SimpleNamespace

    def _shared_get_current_user() -> Any:  # type: ignore[misc]
        return SimpleNamespace(id="dev-user", role="admin")

    def _shared_require_project_member(project_id: str) -> Any:  # type: ignore[misc]
        return _shared_get_current_user()

    def _shared_require_project_role(project_id: str, allowed: set[str]) -> Any:  # type: ignore[misc]
        return _shared_get_current_user()


def get_current_user() -> Any:
    return _shared_get_current_user()


def require_project_member(project_id: str) -> Any:
    return _shared_require_project_member(project_id)


def require_editor(project_id: str) -> Any:
    """Create/edit PYC drafts and BBNT drafts."""
    return _shared_require_project_role(project_id, {"project_manager", "engineer"})


def require_confirmer(project_id: str) -> Any:
    """Only a human with an acceptance-confirmation role may confirm.

    The shared permission grant ("người được cấp quyền nghiệm thu") is not part
    of the current core.  Until Codex adds it, project managers/admins are the
    only allowed confirmers.  AI/automation must never call this endpoint.
    """
    return _shared_require_project_role(project_id, {"project_manager"})


def current_user_id(user: Any) -> Optional[str]:
    return getattr(user, "id", None)
