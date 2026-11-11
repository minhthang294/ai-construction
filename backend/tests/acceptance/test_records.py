"""BBNT draft, tri-state checklist and human confirmation tests."""
from __future__ import annotations

from fastapi import HTTPException

from app.acceptance.dependencies import require_confirmer
from app.acceptance.models import AcceptanceAuditLog
from conftest import (
    create_record,
    create_request,
    record_payload,
    seed_document_page,
    seed_photo,
    seed_source_document,
)


def test_draft_record_seeds_explicit_unconfirmed_checklist(client):
    request = create_request(client)
    record = create_record(client, request["id"], checklist=[])
    assert record["status"] == "draft"
    assert record["result"] is None
    assert record["confirmer_id"] is None
    assert len(record["checklist"]) == 7
    assert {item["state"] for item in record["checklist"]} == {"unconfirmed"}


def test_duplicate_record_for_request_is_rejected(client):
    request = create_request(client)
    create_record(client, request["id"])
    response = client.post(
        "/api/v1/projects/p1/acceptance-records", json=record_payload(request["id"])
    )
    assert response.status_code == 409
    assert response.json()["code"] == "record_exists"


def test_confirm_requires_every_checklist_item_resolved(client):
    request = create_request(client)
    record = create_record(
        client,
        request["id"],
        checklist=[
            {"item": "Đã xác nhận", "state": "yes"},
            {"item": "Chưa xác nhận", "state": "unconfirmed"},
        ],
    )
    response = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "checklist_unconfirmed"
    fetched = client.get(f"/api/v1/projects/p1/acceptance-records/{record['id']}")
    assert fetched.json()["status"] == "draft"


def test_confirmation_is_human_and_role_checked(client):
    request = create_request(client)
    record = create_record(client, request["id"])

    def deny(project_id):
        raise HTTPException(status_code=403, detail="Insufficient project role")

    client.app.dependency_overrides[require_confirmer] = deny
    try:
        response = client.post(
            f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
            json={"result": "approved"},
        )
    finally:
        client.app.dependency_overrides[require_confirmer] = lambda project_id: client.actor
    assert response.status_code == 403
    fetched = client.get(f"/api/v1/projects/p1/acceptance-records/{record['id']}")
    assert fetched.json()["status"] == "draft"


def test_human_confirmation_sets_result_and_audit(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    response = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert response.status_code == 200, response.text
    confirmed = response.json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["result"] == "approved"
    assert confirmed["confirmer_id"] == client.actor.id
    assert confirmed["confirmed_at"] is not None

    with client.SessionLocal() as db:
        audits = db.query(AcceptanceAuditLog).filter_by(entity="AcceptanceRecord").all()
        assert any(row.action == "confirm" and row.entity_id == record["id"] for row in audits)


def test_approved_is_inconsistent_when_quality_item_fails(client):
    request = create_request(client)
    record = create_record(client, request["id"], design_compliance="no")
    response = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "result_inconsistent"


def test_conditional_requires_a_reason_and_can_be_confirmed(client):
    request = create_request(client)
    record = create_record(client, request["id"])

    missing = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "conditional"},
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "conclusion_note_required"

    ok = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "conditional", "conclusion_note": "Bổ sung hồ sơ thí nghiệm"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["result"] == "conditional"
    assert ok.json()["conclusion_note"] == "Bổ sung hồ sơ thí nghiệm"


def test_confirmed_record_cannot_be_edited_or_reconfirmed(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    assert client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    ).status_code == 200

    patch = client.patch(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}",
        json={"other_notes": "changed"},
    )
    assert patch.status_code == 409
    assert patch.json()["code"] == "record_confirmed"

    again = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "record_already_confirmed"


def test_record_update_replaces_tristate_checklist(client):
    request = create_request(client)
    record = create_record(client, request["id"], checklist=[])
    photo = seed_photo(client, "p1", confirmed_caption="Ảnh đã xác nhận")
    response = client.patch(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}",
        json={
            "checklist": [
                {"item": "Một", "state": "yes", "evidence_refs": [photo]},
                {"item": "Hai", "state": "no", "note": "Thiếu"},
                {"item": "Ba", "state": "unconfirmed"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    states = [item["state"] for item in response.json()["checklist"]]
    assert states == ["yes", "no", "unconfirmed"]
    assert response.json()["checklist"][0]["evidence_refs"] == [photo]


def _record_with_evidence(evidence_ref):
    return record_payload(
        request_id="",
        checklist=[{"item": "Hình ảnh", "state": "yes", "evidence_refs": [evidence_ref]}],
    )


def test_evidence_photo_must_belong_to_the_project(client):
    request = create_request(client)
    other_photo = seed_photo(
        client, "p2", confirmed_caption="Ảnh công trình khác", filename="other.jpg"
    )
    payload = _record_with_evidence(other_photo)
    payload["request_id"] = request["id"]
    response = client.post("/api/v1/projects/p1/acceptance-records", json=payload)
    assert response.status_code == 404
    assert response.json()["code"] == "evidence_photo_not_found"


def test_evidence_photo_must_be_human_confirmed(client):
    request = create_request(client)
    unconfirmed = seed_photo(client, "p1", filename="unconfirmed.jpg")
    payload = _record_with_evidence(unconfirmed)
    payload["request_id"] = request["id"]
    response = client.post("/api/v1/projects/p1/acceptance-records", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "evidence_photo_unconfirmed"


def test_confirmed_photo_evidence_is_accepted_and_preserved(client):
    request = create_request(client)
    photo = seed_photo(client, "p1", confirmed_caption="Móng cọc đã nghiệm thu")
    payload = _record_with_evidence(photo)
    payload["request_id"] = request["id"]
    response = client.post("/api/v1/projects/p1/acceptance-records", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["checklist"][0]["evidence_refs"] == [photo]

    category_photo = seed_photo(client, "p1", category="issue", filename="category.jpg")
    updated = client.patch(
        f"/api/v1/projects/p1/acceptance-records/{response.json()['id']}",
        json={
            "checklist": [
                {"item": "Hình ảnh", "state": "yes", "evidence_refs": [category_photo]}
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["checklist"][0]["evidence_refs"] == [category_photo]


def test_engineering_source_document_and_page_evidence_are_accepted(client):
    request = create_request(client)
    document = seed_source_document(client, "p1")
    page_one = seed_document_page(client, document, "p1", page_number=1)
    seed_document_page(client, document, "p1", page_number=2)
    refs = [
        f"document:{document}",
        f"page:{page_one}",
        f"page:{document}:1",
        f"page:{document}#2",
    ]
    response = client.post(
        "/api/v1/projects/p1/acceptance-records",
        json=record_payload(
            request["id"],
            checklist=[{"item": "Hồ sơ thiết kế", "state": "yes", "evidence_refs": refs}],
        ),
    )
    assert response.status_code == 201, response.text
    assert response.json()["checklist"][0]["evidence_refs"] == refs


def test_engineering_evidence_refs_are_project_scoped(client):
    request = create_request(client)
    other_document = seed_source_document(client, "p2")
    other_page = seed_document_page(client, other_document, "p2")

    for ref, code in (
        (f"document:{other_document}", "evidence_document_not_found"),
        (f"page:{other_page}", "evidence_page_not_found"),
        (f"page:{other_document}:1", "evidence_document_not_found"),
    ):
        response = client.post(
            "/api/v1/projects/p1/acceptance-records",
            json=record_payload(
                request["id"],
                checklist=[{"item": "Hồ sơ thiết kế", "state": "yes", "evidence_refs": [ref]}],
            ),
        )
        assert response.status_code == 404, (ref, response.text)
        assert response.json()["code"] == code


def test_unresolved_or_malformed_evidence_refs_are_rejected(client):
    request = create_request(client)
    missing_photo = client.post(
        "/api/v1/projects/p1/acceptance-records",
        json=record_payload(
            request["id"],
            checklist=[
                {"item": "Ảnh", "state": "yes", "evidence_refs": ["arbitrary-unresolved-id"]}
            ],
        ),
    )
    assert missing_photo.status_code == 404
    assert missing_photo.json()["code"] == "evidence_photo_not_found"

    document = seed_source_document(client, "p1")
    seed_document_page(client, document, "p1", page_number=1)
    page_missing = client.post(
        "/api/v1/projects/p1/acceptance-records",
        json=record_payload(
            request["id"],
            checklist=[
                {
                    "item": "Trang",
                    "state": "yes",
                    "evidence_refs": [f"page:{document}:2"],
                }
            ],
        ),
    )
    assert page_missing.status_code == 404
    assert page_missing.json()["code"] == "evidence_page_not_found"

    for ref in ("unknown:abc", f"page:{document}:bad", ""):
        response = client.post(
            "/api/v1/projects/p1/acceptance-records",
            json=record_payload(
                request["id"],
                checklist=[{"item": "Sai", "state": "yes", "evidence_refs": [ref]}],
            ),
        )
        assert response.status_code == 422, (ref, response.text)
        assert response.json()["code"] == "evidence_ref_invalid"


def test_record_reuses_pyc_participant_names_without_inventing(client):
    request = create_request(client)
    payload = record_payload(request["id"])
    payload.pop("participants")
    response = client.post("/api/v1/projects/p1/acceptance-records", json=payload)
    assert response.status_code == 201, response.text
    record = response.json()
    participants = {
        (item["role"], item["person_name"]) for item in record["participants"]
    }
    assert ("investor", "Người chủ đầu tư") in participants
    assert ("supervisor", "Người giám sát") in participants
    assert ("contractor", "Người yêu cầu") in participants
    assert record["result"] is None
