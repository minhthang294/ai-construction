from datetime import date
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from app.core.models import Project
from app.site.service import (
    GENERIC_REPORT_TITLE,
    format_report_date,
    resolve_project_title,
    work_item_names,
)


def test_resolve_project_title_prefers_configured_title():
    project = SimpleNamespace(report_title="  BÁO CÁO CÔNG TRÌNH A  ", name="Cầu A")
    assert resolve_project_title(project) == "BÁO CÁO CÔNG TRÌNH A"


def test_resolve_project_title_falls_back_to_project_name_then_generic():
    assert resolve_project_title(SimpleNamespace(report_title="", name="Cầu A")) == "Cầu A"
    assert resolve_project_title(SimpleNamespace(report_title=None, name="  ")) == (
        GENERIC_REPORT_TITLE
    )
    assert resolve_project_title(None) == GENERIC_REPORT_TITLE


def test_format_report_date_uses_vietnamese_order():
    assert format_report_date(date(2026, 1, 2)) == "02/01/2026"
    assert format_report_date(date(2026, 11, 11)) == "11/11/2026"


def test_work_item_names_are_resolved_only_inside_the_project(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        names = work_item_names(db, "p1", ["w1", "w-other", "missing"])
    assert names == {"w1": "Work item 1"}


def test_zalo_export_uses_project_report_title(client, db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        project = db.get(Project, "p1")
        assert project is not None
        project.report_title = "BÁO CÁO CÔNG TRÌNH A"
        db.commit()

    saved = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-11",
        json={
            "status": "reviewed",
            "notes": None,
            "manpower": [],
            "work_logs": [],
            "next_day_plans": [],
        },
    )
    assert saved.status_code == 200, saved.text
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports",
        json={"format": "zalo"},
    )
    assert r.status_code == 201, r.text
    preview = r.json()["preview_text"]
    assert preview.startswith("BÁO CÁO CÔNG TRÌNH A\nNgày: 11/11/2026")
    assert "1. Nhân lực" in preview
    assert "4. Hình ảnh" in preview
    # No plans were entered: the heading must not infer a plan date.
    assert "3. Dự kiến công việc ngày kế tiếp" in preview
    assert "3. Dự kiến công việc ngày 12/11/2026" not in preview


def test_zalo_plan_dates_are_shown_per_item_when_dates_differ(client):
    saved = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-20",
        json={
            "status": "reviewed",
            "notes": None,
            "manpower": [],
            "work_logs": [],
            "next_day_plans": [
                {"plan_date": "2026-11-21", "description": "Plan A"},
                {"plan_date": "2026-11-22", "description": "Plan B"},
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-20/exports",
        json={"format": "zalo"},
    )
    assert r.status_code == 201, r.text
    preview = r.json()["preview_text"]
    assert "3. Dự kiến công việc ngày kế tiếp" in preview
    plan_section = preview.split("3. Dự kiến công việc", 1)[1].split(
        "4. Hình ảnh", 1
    )[0]
    assert "- 21/11/2026: Plan A" in plan_section
    assert "- 22/11/2026: Plan B" in plan_section
