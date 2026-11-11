import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Storage and database must be configured before app modules are imported.
os.environ["SITE_REPORT_STORAGE"] = tempfile.mkdtemp(prefix="site-report-tests-")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{Path(tempfile.mkdtemp(prefix='site-report-db-')) / 'shared.db'}",
)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.site.models import Base
from app.site.router import router, get_db
from app.site.dependencies import (
    get_current_user,
    require_project_member,
    require_site_editor,
)

# Register the shared tables (users/projects/work_items/audit_logs) on the same
# SQLAlchemy metadata so project-scoped work-item validation and audit hooks can
# be exercised.  The module still imports when shared core is absent.
try:  # pragma: no cover - shared core exists in this repository
    from app.core.models import Organization, Project, User, WorkItem  # noqa: F401
except Exception:  # pragma: no cover
    Organization = Project = User = WorkItem = None  # type: ignore[assignment]


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    if Project is not None and User is not None and WorkItem is not None:
        Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with Session() as db:
            db.add(Project(id="p1", name="Test project"))
            db.add(User(id="test-user", username="test-user", password_hash="x", role="engineer"))
            db.add(WorkItem(id="w1", project_id="p1", code="W1", name="Work item 1"))
            db.add(WorkItem(id="w-other", project_id="other", code="WX", name="Other project item"))
            if Organization is not None:
                db.add(Organization(id="org1", project_id="p1", name="Org 1"))
                db.add(
                    Organization(
                        id="org-other", project_id="other", name="Other project org"
                    )
                )
            db.commit()

    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_engine):
    SessionLocal = sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, future=True
    )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: type(
        "U", (), {"id": "test-user", "role": "engineer"}
    )()
    app.dependency_overrides[require_project_member] = lambda project_id: type(
        "U", (), {"id": "test-user", "role": "engineer"}
    )()
    app.dependency_overrides[require_site_editor] = lambda project_id: type(
        "U", (), {"id": "test-user", "role": "engineer"}
    )()
    with TestClient(app) as test_client:
        yield test_client
