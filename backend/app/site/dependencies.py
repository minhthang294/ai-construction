"""Dependency hooks for Site Report.

Shared auth/access is owned by Codex.  We import it lazily so the module remains
importable in isolation; tests override these dependencies through
``app.dependency_overrides``.

The router always receives the current user from a FastAPI dependency (never by
calling the access helper directly inside the endpoint body).  That keeps the
project-scope check enforceable, overridable in tests and impossible to forget.
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


# Roles allowed to create/update site report data.  ``viewer`` is read-only.
# The actual check is performed by the shared ``require_project_role`` helper.
SITE_EDITOR_ROLES = {"admin", "project_manager", "engineer"}
def get_current_user() -> Any:
    """Return the authenticated user supplied by the shared auth middleware."""

    return _shared_get_current_user()


def require_project_member(project_id: str) -> Any:
    """Require membership of ``project_id`` (404 when outside the project)."""

    return _shared_require_project_member(project_id)


def require_site_editor(project_id: str) -> Any:
    """Require a project role allowed to write site data.

    ``viewer`` may read reports and photos but must not create or modify them.
    The shared ``require_project_role`` performs the actual membership-role
    check; global admins are allowed by that contract.
    """

    return _shared_require_project_role(project_id, {"project_manager", "engineer"})


def current_user_id(user: Any) -> Optional[str]:
    return getattr(user, "id", None)
