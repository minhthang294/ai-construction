"""BBNT reuse, stale detection and append-only revisions."""
from __future__ import annotations

import openpyxl

from conftest import (
    create_record,
    create_request,
    record_payload,
    seed_daily_report,
    seed_photo,
    seed_source_document,
    seed_work_item,
)


def _profiles(client):
    result = {}
    for role, name in (
        ("requester", "Người yêu cầu"),
        ("supervisor", "Người giám sát"),
        ("investor", "Người chủ đầu tư"),
    ):
        response = client.post(
            "/api/v1/projects/p1/acceptance-participants",
            json={
                "full_name": name,
                "organization": f"Đơn vị {role}",
                "position": role,
                "role": role,
                "active": True,
            },
        )
        assert response.status_code == 201, response.text
        result[role] = response.json()["id"]
    return result


def _request_with_reuse(client):
    work_item = seed_work_item(client, "p1", code="W-REUSE", name="Hạng mục tái sử dụng")
    report = seed_daily_report(client, "p1", notes="Báo cáo dùng cho BBNT")
    photo = seed_photo(
        client,
        "p1",
        confirmed_caption="Ảnh đã xác nhận",
        filename="reuse.jpg",
        report_id=report,
    )
    document = seed_source_document(client, "p1", original_name="Bản vẽ thi công.pdf")
    profiles = _profiles(client)
    request = create_request(
        client,
        work_item_id=work_item,
        daily_report_id=report,
        request_date="2026-11-11",
        inspection_time="09h30",
        requested_by_profile_id=profiles["requester"],
        supervisor_profile_id=profiles["supervisor"],
        investor_profile_id=profiles["investor"],
    )
    return request, work_item, report, photo, document


def _record_without_manual_fields(request_id):
    payload = record_payload(request_id)
    for key in ("record_date", "start_time", "participants", "checklist"):
        payload.pop(key)
    return payload


def test_bbnt_reuses_pyc_data_without_manual_reentry(client):
    request, work_item, report, photo, document = _request_with_reuse(client)
    response = client.post(
        "/api/v1/projects/p1/acceptance-records",
        json=_record_without_manual_fields(request["id"]),
    )
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["number"] == request["number"]
    assert record["record_date"] == "2026-11-11"
    assert record["start_time"] == "09h30"
    assert record["request_updated_at"] is not None
    assert record["stale"] is False
    assert record["reused"]["work_item_id"] == work_item
    assert record["reused"]["work_item_name"] == "Hạng mục tái sử dụng"
    assert record["reused"]["daily_report_id"] == report
    assert photo in record["reused"]["confirmed_photos"]
    assert document in {
        item["id"] for item in record["reused"]["technical_documents"]
    }
    assert {item["person_name"] for item in record["participants"]} == {
        "Người yêu cầu",
        "Người giám sát",
        "Người chủ đầu tư",
    }
    assert record["result"] is None
    assert {item["state"] for item in record["checklist"]} == {"unconfirmed"}


def test_pyc_change_marks_record_stale_without_mutating_it(client):
    request, _, _, _, _ = _request_with_reuse(client)
    record = create_record(
        client,
        request["id"],
        participants=record_payload(request["id"])["participants"],
    )
    assert record["stale"] is False

    changed = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}",
        json={"content": "Nội dung PYC đã thay đổi sau khi lập BBNT"},
    )
    assert changed.status_code == 200, changed.text

    fetched = client.get(f"/api/v1/projects/p1/acceptance-records/{record['id']}")
    assert fetched.status_code == 200
    stale = fetched.json()
    assert stale["stale"] is True
    assert "PYC đã thay đổi" in stale["stale_warning"]
    assert stale["other_notes"] == record["other_notes"]
    assert stale["result"] == record["result"]


def test_confirmed_record_stays_immutable_and_stale(client):
    request, _, _, _, _ = _request_with_reuse(client)
    record = create_record(client, request["id"])
    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["stale"] is False

    client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}",
        json={"content": "Thay đổi sau xác nhận"},
    )
    fetched = client.get(f"/api/v1/projects/p1/acceptance-records/{record['id']}")
    assert fetched.json()["stale"] is True
    assert fetched.json()["status"] == "confirmed"
    assert fetched.json()["result"] == "approved"

    edit = client.patch(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}",
        json={"other_notes": "Không được sửa"},
    )
    assert edit.status_code == 409
    assert edit.json()["code"] == "record_confirmed"


def test_issued_bbnt_preview_and_export_freeze_pyc_snapshot(client, tmp_path):
    request = create_request(client, number="94", location="Vị trí ban đầu")
    record = create_record(client, request["id"])
    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text

    changed = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}",
        json={"location": "Vị trí đã sửa sau khi phát hành"},
    )
    assert changed.status_code == 200, changed.text

    fetched = client.get(f"/api/v1/projects/p1/acceptance-records/{record['id']}")
    assert fetched.json()["stale"] is True

    preview = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/preview"
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["cells"]["BBNT"]["B6"] == "Vị trí ban đầu"
    assert preview.json()["cells"]["PYC"]["B7"] == "Vị trí ban đầu"

    exported = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports",
        json={"kind": "bbnt", "format": "xlsx"},
    )
    assert exported.status_code == 201, exported.text
    download = client.get(exported.json()["download_url"])
    assert download.status_code == 200
    path = tmp_path / "issued-bbnt.xlsx"
    path.write_bytes(download.content)
    workbook = openpyxl.load_workbook(path)
    assert workbook["BBNT"]["B6"].value == "Vị trí ban đầu"
    assert workbook["PYC"]["B7"].value == "Vị trí ban đầu"

    revised = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/revisions"
    )
    assert revised.status_code == 201, revised.text
    revised_preview = client.get(
        f"/api/v1/projects/p1/acceptance-records/{revised.json()['id']}/preview"
    )
    assert revised_preview.status_code == 200
    assert revised_preview.json()["cells"]["BBNT"]["B6"] == "Vị trí đã sửa sau khi phát hành"


def test_revision_copies_record_without_auto_conclusion(client):
    request, _, _, _, _ = _request_with_reuse(client)
    original = create_record(
        client,
        request["id"],
        participants=record_payload(request["id"])["participants"],
        checklist=[
            {"item": "Hồ sơ", "state": "yes", "evidence_refs": []},
            {"item": "Kiểm tra", "state": "yes", "evidence_refs": []},
        ],
    )
    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{original['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text

    revised = client.post(
        f"/api/v1/projects/p1/acceptance-records/{original['id']}/revisions"
    )
    assert revised.status_code == 201, revised.text
    new = revised.json()
    assert new["revision"] == 2
    assert new["supersedes_id"] == original["id"]
    assert new["status"] == "draft"
    assert new["result"] is None
    assert new["confirmer_id"] is None
    assert new["number"] == f"{request['number']}-R2"
    assert [
        (item["role"], item["person_name"], item["organization"], item["position"])
        for item in new["participants"]
    ] == [
        (item["role"], item["person_name"], item["organization"], item["position"])
        for item in original["participants"]
    ]
    assert {item["state"] for item in new["checklist"]} == {"unconfirmed"}

    old = client.get(f"/api/v1/projects/p1/acceptance-records/{original['id']}")
    assert old.status_code == 200
    assert old.json()["status"] == "confirmed"
    assert old.json()["result"] == "approved"
    assert old.json()["revision"] == 1
