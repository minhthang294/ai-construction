import io
import json
import zipfile


def _payload(work_logs, status="reviewed"):
    return {
        "status": status,
        "notes": None,
        "manpower": [],
        "work_logs": work_logs,
        "next_day_plans": [],
    }


def _export(client, date, fmt="zalo"):
    response = client.post(
        f"/api/v1/projects/p1/daily-reports/{date}/exports",
        json={"format": fmt},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_put_work_name_without_work_item_id_roundtrips_and_exports(client):
    saved = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-25",
        json=_payload(
            [
                {
                    "work_name": "Đục bỏ bê tông om vỡ",
                    "location": "Cọc A2, A8",
                    "status": "done",
                }
            ]
        ),
    )
    assert saved.status_code == 200, saved.text
    work_log = saved.json()["work_logs"][0]
    assert work_log["work_name"] == "Đục bỏ bê tông om vỡ"
    assert work_log["work_item_id"] is None

    fetched = client.get("/api/v1/projects/p1/daily-reports/2026-11-25")
    assert fetched.status_code == 200
    assert fetched.json()["work_logs"][0]["work_name"] == "Đục bỏ bê tông om vỡ"

    preview = _export(client, "2026-11-25")["preview_text"]
    assert "- Đục bỏ bê tông om vỡ tại Cọc A2, A8 (Hoàn thành)" in preview

    zip_export = _export(client, "2026-11-25", "zip")
    download = client.get(zip_export["download_url"])
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        snapshot = json.loads(archive.read("snapshot.json"))
    item = snapshot["work_logs"][0]
    # Without a catalog id the unique stored name is the display name.
    assert item["work_item_name"] == "Đục bỏ bê tông om vỡ"
    assert item["work_name"] == "Đục bỏ bê tông om vỡ"
    assert item["work_item_id"] is None


def test_legacy_work_item_id_still_resolves_name_for_export(client):
    saved = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-26",
        json=_payload(
            [
                {
                    "work_item_id": "w1",
                    "location": "Trụ T1",
                    "status": "done",
                }
            ]
        ),
    )
    assert saved.status_code == 200, saved.text
    work_log = saved.json()["work_logs"][0]
    assert work_log["work_item_id"] == "w1"
    assert work_log["work_name"] is None

    preview = _export(client, "2026-11-26")["preview_text"]
    assert "- Work item 1 tại Trụ T1 (Hoàn thành)" in preview

    zip_export = _export(client, "2026-11-26", "zip")
    download = client.get(zip_export["download_url"])
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        snapshot = json.loads(archive.read("snapshot.json"))
    assert snapshot["work_logs"][0]["work_item_name"] == "Work item 1"


def test_work_log_uses_component_when_location_is_empty(client):
    saved = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-27",
        json=_payload(
            [
                {
                    "work_name": "Khoan cấy thép",
                    "component": "Dầm D1",
                    "status": "done",
                }
            ]
        ),
    )
    assert saved.status_code == 200, saved.text

    preview = _export(client, "2026-11-27")["preview_text"]
    assert "- Khoan cấy thép tại Dầm D1 (Hoàn thành)" in preview
