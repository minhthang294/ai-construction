"""PYC request API tests."""
from __future__ import annotations

from conftest import create_request, request_payload, seed_daily_report, seed_work_item


def test_create_list_and_get_request(client):
    created = create_request(client)
    assert created["number"] == "32"
    assert created["status"] == "draft"
    assert created["project_name"] == "Công trình thử nghiệm"

    listed = client.get("/api/v1/projects/p1/acceptance-requests")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

    fetched = client.get(f"/api/v1/projects/p1/acceptance-requests/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_duplicate_number_conflicts(client):
    create_request(client)
    response = client.post("/api/v1/projects/p1/acceptance-requests", json=request_payload())
    assert response.status_code == 409
    assert response.json()["code"] == "request_number_conflict"


def test_request_is_project_scoped(client):
    created = create_request(client)
    response = client.get(f"/api/v1/projects/p2/acceptance-requests/{created['id']}")
    assert response.status_code == 404


def test_submit_requires_validated_fields(client):
    created = create_request(client, content=None, location=None, request_date=None)
    response = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"status": "submitted"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "content_required"


def test_submit_with_complete_data(client):
    created = create_request(client)
    response = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"status": "submitted"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "submitted"


def test_invalid_field_value_is_rejected_by_schema(client):
    response = client.post(
        "/api/v1/projects/p1/acceptance-requests",
        json=request_payload(field="unknown"),
    )
    assert response.status_code == 422


def test_work_item_must_belong_to_the_project(client):
    in_project = seed_work_item(client, "p1", code="W1", name="Trong công trình")
    other_project = seed_work_item(client, "p2", code="W2", name="Công trình khác")

    ok = create_request(client, number="33", work_item_id=in_project)
    assert ok["work_item_id"] == in_project

    response = client.post(
        "/api/v1/projects/p1/acceptance-requests",
        json=request_payload(number="34", work_item_id=other_project),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "work_item_not_found"


def test_work_item_update_is_project_scoped(client):
    created = create_request(client, number="35")
    other_project = seed_work_item(client, "p2", code="W3", name="Công trình khác")

    rejected = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"work_item_id": other_project},
    )
    assert rejected.status_code == 404
    assert rejected.json()["code"] == "work_item_not_found"

    missing = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"work_item_id": "does-not-exist"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "work_item_not_found"

    in_project = seed_work_item(client, "p1", code="W4", name="Trong công trình")
    accepted = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"work_item_id": in_project},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["work_item_id"] == in_project


def test_daily_report_must_belong_to_the_project(client):
    in_project = seed_daily_report(client, "p1", notes="Báo cáo trong công trình")
    other_project = seed_daily_report(client, "p2", notes="Báo cáo công trình khác")

    created = create_request(client, number="36", daily_report_id=in_project)
    assert created["daily_report_id"] == in_project

    rejected = client.post(
        "/api/v1/projects/p1/acceptance-requests",
        json=request_payload(number="37", daily_report_id=other_project),
    )
    assert rejected.status_code == 404
    assert rejected.json()["code"] == "daily_report_not_found"

    missing = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"daily_report_id": "does-not-exist"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "daily_report_not_found"

    accepted = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"daily_report_id": in_project},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["daily_report_id"] == in_project

    linked = client.get(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}/daily-report"
    )
    assert linked.status_code == 200
    assert linked.json()["id"] == in_project
    assert linked.json()["report_date"] == "2026-11-11"
    assert linked.json()["notes"] == "Báo cáo trong công trình"


def test_daily_report_link_can_be_absent(client):
    created = create_request(client, number="38")
    response = client.get(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}/daily-report"
    )
    assert response.status_code == 200
    assert response.json() is None
