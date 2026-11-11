from datetime import date

import pytest

from app.engineering_ai.models import Base


@pytest.fixture()
def shared_tables(db_engine):
    from app.core.models import WorkItem
    from app.site.models import DailyReport, DailyWorkLog, ManpowerEntry, NextDayPlan

    Base.metadata.create_all(db_engine)
    return {
        "DailyReport": DailyReport,
        "ManpowerEntry": ManpowerEntry,
        "DailyWorkLog": DailyWorkLog,
        "NextDayPlan": NextDayPlan,
        "WorkItem": WorkItem,
    }


def _provided_report():
    return {
        "report": {
            "status": "draft",
            "report_date": "2026-11-11",
            "notes": "Ghi chú đã có",
            "manpower": [
                {"group_name": "Tổ A", "count": 0},
                {"group_name": "Tổ B", "count": None},
            ],
            "work_logs": [
                {
                    "location": "Trụ 1",
                    "component": "Bê tông",
                    "quantity": None,
                    "unit": None,
                },
                {
                    "work_item_id": "wi-1",
                    "location": "Trụ 2",
                    "component": "Cốt thép",
                    "quantity": 1.5,
                    "unit": "t",
                },
            ],
            "next_day_plans": [
                {
                    "plan_date": "2026-11-12",
                    "description": "Đổ bê tông trụ 2",
                    "manpower": "5 người",
                    "equipment": "Máy bơm",
                }
            ],
        }
    }


def test_provided_report_draft_preserves_recorded_data_only(client):
    response = client.post(
        "/api/v1/projects/p1/ai/daily-report-drafts",
        json=_provided_report(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "provided"
    assert body["source_status"] == "draft"
    assert body["no_invented_quantities"] is True
    assert [entry["count"] for entry in body["draft"]["manpower"]] == [0, None]
    assert body["draft"]["work_logs"][0]["quantity"] is None
    assert body["draft"]["work_logs"][1]["quantity"] == 1.5
    assert any("0 người" in line for line in body["draft"]["summary_lines"])
    assert any("chưa ghi số lượng" in line for line in body["draft"]["summary_lines"])
    assert not any("None" in line for line in body["draft"]["summary_lines"])

    missing = {(item["section"], item.get("index"), item["field"]) for item in body["missing_fields"]}
    assert ("manpower", 1, "count") in missing
    assert ("work_logs", 0, "quantity") in missing
    assert ("work_logs", 1, "quantity") not in missing
    assert ("work_logs", 0, "location") not in missing
    assert body["disclaimer"]


def test_daily_report_draft_requires_exactly_one_source(client):
    response = client.post(
        "/api/v1/projects/p1/ai/daily-report-drafts",
        json={**_provided_report(), "report_id": "report-1"},
    )
    assert response.status_code == 422

    response = client.post("/api/v1/projects/p1/ai/daily-report-drafts", json={})
    assert response.status_code == 422


def test_linked_draft_and_reviewed_report_are_read_only(
    client, session_factory, shared_tables
):
    DailyReport = shared_tables["DailyReport"]
    ManpowerEntry = shared_tables["ManpowerEntry"]
    DailyWorkLog = shared_tables["DailyWorkLog"]
    NextDayPlan = shared_tables["NextDayPlan"]

    with session_factory() as db:
        report = DailyReport(
            project_id="p1",
            report_date=date(2026, 11, 11),
            status="reviewed",
            notes="Nguồn đã xem",
        )
        db.add(report)
        db.flush()
        db.add_all(
            [
                ManpowerEntry(
                    report_id=report.id,
                    project_id="p1",
                    group_name="Tổ C",
                    count=3,
                ),
                DailyWorkLog(
                    report_id=report.id,
                    project_id="p1",
                    work_item_id="wi-1",
                    location="Mố M1",
                    component="Cốp pha",
                    quantity=0.0,
                    unit="m2",
                ),
                NextDayPlan(
                    report_id=report.id,
                    project_id="p1",
                    plan_date=date(2026, 11, 12),
                    description="Tháo cốp pha",
                    manpower="2",
                    equipment="Cần cẩu",
                ),
            ]
        )
        db.commit()
        report_id = report.id

    before = None
    with session_factory() as db:
        before = db.get(DailyReport, report_id).status

    response = client.post(
        "/api/v1/projects/p1/ai/daily-report-drafts",
        json={"report_id": report_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "linked"
    assert body["source_report_id"] == report_id
    assert body["source_status"] == "reviewed"
    assert body["draft"]["manpower"][0]["count"] == 3
    assert body["draft"]["work_logs"][0]["quantity"] == 0.0
    assert body["draft"]["next_day_plans"][0]["description"] == "Tháo cốp pha"
    assert body["missing_fields"] == []

    with session_factory() as db:
        assert db.get(DailyReport, report_id).status == before


def test_linked_report_is_project_scoped(client, session_factory, shared_tables):
    DailyReport = shared_tables["DailyReport"]
    with session_factory() as db:
        report = DailyReport(
            project_id="p1",
            report_date=date(2026, 11, 11),
            status="draft",
        )
        db.add(report)
        db.commit()
        report_id = report.id

    response = client.post(
        "/api/v1/projects/p2/ai/daily-report-drafts",
        json={"report_id": report_id},
    )
    assert response.status_code == 404


def test_inspection_suggestions_are_citation_grounded_and_unconfirmed(client, digital_document):
    response = client.post(
        "/api/v1/projects/p1/ai/inspection-checklists",
        json={
            "work_item": {
                "code": "WI-01",
                "name": "abutment concrete cover",
                "component": "abutment",
            },
            "top_k": 6,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_sources"] is True
    assert body["no_source"] is False
    assert body["suggestions"]
    assert body["work_item"]["code"] == "WI-01"
    assert body["disclaimer"]

    for suggestion in body["suggestions"]:
        assert suggestion["status"] == "unconfirmed"
        assert suggestion["requires_engineer_review"] is True
        assert suggestion["auto_approved"] is False
        assert "approved" not in suggestion
        assert suggestion["criterion"]
        citation = suggestion["citation"]
        assert citation["document_id"] == digital_document["id"]
        assert citation["page_number"] >= 1
        assert citation["quote"]
        page = client.get(citation["url"]).json()
        assert citation["quote"] in page["text"]


def test_inspection_without_sources_returns_fixed_refusal(client):
    response = client.post(
        "/api/v1/projects/p1/ai/inspection-checklists",
        json={"work_item": {"code": "WI-01", "name": "abutment concrete cover"}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["suggestions"] == []
    assert body["has_sources"] is False
    assert body["no_source"] is True
    assert body["message"] == "Không tìm thấy thông tin này trong hồ sơ công trình hiện có."


def test_inspection_linked_work_item_is_project_scoped(
    client, digital_document, session_factory, shared_tables
):
    WorkItem = shared_tables["WorkItem"]
    with session_factory() as db:
        item = WorkItem(
            project_id="p1",
            code="WI-LINKED",
            name="abutment concrete cover",
            component="abutment",
        )
        db.add(item)
        db.commit()
        item_id = item.id

    response = client.post(
        "/api/v1/projects/p1/ai/inspection-checklists",
        json={"work_item_id": item_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["work_item"]["id"] == item_id
    assert response.json()["suggestions"]

    cross = client.post(
        "/api/v1/projects/p2/ai/inspection-checklists",
        json={"work_item_id": item_id},
    )
    assert cross.status_code == 404
