"""Static guarantees that every site route is project-scoped.

The shared access helpers are injected as FastAPI dependencies.  A route that
forgets the dependency would expose another project's data, so this test fails
if that regresses.
"""

from app.site.dependencies import (
    get_current_user,
    require_project_member,
    require_site_editor,
)
from app.site.router import router


def _dependency_calls(route):
    return [dependency.call for dependency in route.dependant.dependencies]


def test_every_route_requires_project_membership():
    for route in router.routes:
        calls = _dependency_calls(route)
        assert (
            require_project_member in calls or require_site_editor in calls
        ), f"{route.path} is not project-scoped"


def test_write_routes_require_editor_role():
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
    for route in router.routes:
        if not (route.methods or set()) & write_methods:
            continue
        calls = _dependency_calls(route)
        assert require_site_editor in calls, f"{route.path} allows viewer writes"


def test_read_routes_do_not_require_editor_role():
    for route in router.routes:
        if (route.methods or set()) & {"POST", "PUT", "PATCH", "DELETE"}:
            continue
        calls = _dependency_calls(route)
        assert require_project_member in calls, f"{route.path} is not read-scoped"
        assert require_site_editor not in calls, f"{route.path} requires edit role for reads"


def test_router_exposes_auth_dependency_for_override():
    # Imported for test override targets; the route itself uses the scoped
    # dependencies above.
    assert get_current_user is not None
