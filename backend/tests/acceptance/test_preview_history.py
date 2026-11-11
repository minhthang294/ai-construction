"""Preview payloads and work-item acceptance history."""
from __future__ import annotations

import os
from pathlib import Path

from conftest import (
    create_record,
    create_request,
    seed_work_item,
)


def test_request_preview_returns_template_cells_without_writing_files(client):
    request = create_request(client, number="91")
    storage = Path(os.environ["ACCEPTANCE_STORAGE"])
    before = {str(path) for path in storage.rglob("*")} if storage.exists() else set()

    response = client.get(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/preview"
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["kind"] == "pyc"
    assert preview["source_id"] == request["id"]
    assert preview["cells"]["PYC"]["B6"] == 91
    assert preview["cells"]["PYC"]["A20"] == "Người yêu cầu"
    assert preview["cells"]["PYC"]["H10"] == "☑"
    assert preview["warnings"] == []

    after = {str(path) for path in storage.rglob("*")} if storage.exists() else set()
    assert after == before


def test_bbnt_preview_returns_both_sheets_and_warns_if_unconfirmed(client):
    request = create_request(client, number="92")
    record = create_record(client, request["id"])

    unconfirmed = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/preview"
    )
    assert unconfirmed.status_code == 200
    assert any("chưa được người có quyền xác nhận" in item for item in unconfirmed.json()["warnings"])

    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text
    preview = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/preview"
    ).json()
    assert preview["kind"] == "bbnt"
    assert preview["cells"]["PYC"]["B6"] == 92
    assert preview["cells"]["BBNT"]["B5"] == 92
    assert preview["cells"]["BBNT"]["A36"].endswith("☑")
    assert preview["stale"] is False


def test_work_item_acceptance_history_includes_pyc_and_bbnt(client):
    work_item = seed_work_item(client, "p1", code="W-HIST", name="Hạng mục lịch sử")
    request = create_request(client, number="93", work_item_id=work_item)
    record = create_record(client, request["id"])

    response = client.get(
        f"/api/v1/projects/p1/work-items/{work_item}/acceptance-history"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["work_item_id"] == work_item
    kinds = {item["kind"] for item in body["items"]}
    assert kinds == {"pyc", "bbnt"}
    pyc_item = next(item for item in body["items"] if item["kind"] == "pyc")
    bbnt_item = next(item for item in body["items"] if item["kind"] == "bbnt")
    assert pyc_item["number"] == "93"
    assert pyc_item["revision"] == 1
    assert bbnt_item["number"] == record["number"]
    assert bbnt_item["status"] == "draft"

    foreign = seed_work_item(client, "p2", code="W-OTHER", name="Hạng mục khác")
    rejected = client.get(
        f"/api/v1/projects/p1/work-items/{foreign}/acceptance-history"
    )
    assert rejected.status_code == 404
    assert rejected.json()["code"] == "work_item_not_found"
