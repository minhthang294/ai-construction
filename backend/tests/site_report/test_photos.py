import hashlib
import io
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.site.service import (
    ProjectResourceNotFound,
    _dms_to_deg,
    _exif_datetime_to_utc,
    resolve_photo_path,
)


def _upload(client, data, filename="a.png", **form):
    return client.post(
        "/api/v1/projects/p1/photos",
        files=[("files", (filename, io.BytesIO(data), "image/png"))],
        data=form,
    )


def test_photo_upload_preserves_original_and_metadata(client):
    data = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes" * 10
    r = _upload(client, data, category="progress")
    assert r.status_code == 201, r.text
    photo = r.json()[0]
    assert photo["sha256"] == hashlib.sha256(data).hexdigest()
    assert photo["size_bytes"] == len(data)
    assert photo["category"] == "progress"
    assert photo["gps_confirmed"] is False

    orig = client.get(f"/api/v1/projects/p1/photos/{photo['id']}/original")
    assert orig.status_code == 200
    assert orig.content == data
    assert orig.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in orig.headers["cache-control"]


def test_photo_idempotent_client_upload_id(client):
    data = b"hello-photo"
    r1 = _upload(client, data, filename="b.jpg", client_upload_ids="cid-1")
    r2 = _upload(client, data, filename="b.jpg", client_upload_ids="cid-1")
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()[0]["id"] == r2.json()[0]["id"]
    assert r1.json()[0]["client_upload_id"] == "cid-1"
    assert r1.json()[0]["sync_status"] == "synced"


def test_same_client_upload_id_with_different_bytes_conflicts(client):
    first = _upload(client, b"one", client_upload_ids="cid-conflict")
    assert first.status_code == 201
    second = _upload(client, b"two", client_upload_ids="cid-conflict")
    assert second.status_code == 409


def test_patch_photo_caption_and_explicit_clear(client):
    r = _upload(client, b"img")
    pid = r.json()[0]["id"]
    r2 = client.patch(
        f"/api/v1/projects/p1/photos/{pid}",
        json={"confirmed_caption": "Confirmed", "category": "issue"},
    )
    assert r2.status_code == 200
    assert r2.json()["confirmed_caption"] == "Confirmed"
    assert r2.json()["category"] == "issue"

    # Explicit JSON null clears; an omitted field is unchanged.
    r3 = client.patch(f"/api/v1/projects/p1/photos/{pid}", json={"category": None})
    assert r3.status_code == 200
    assert r3.json()["category"] is None
    assert r3.json()["confirmed_caption"] == "Confirmed"


def test_photo_report_link_must_belong_to_project(client):
    report = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-11",
        json={"manpower": [], "work_logs": [], "next_day_plans": []},
    ).json()

    ok = _upload(client, b"linked", report_id=report["id"])
    assert ok.status_code == 201
    assert ok.json()[0]["report_id"] == report["id"]

    foreign = _upload(client, b"foreign", report_id="missing-report")
    assert foreign.status_code == 404

    listing = client.get(
        "/api/v1/projects/p1/photos", params={"report_id": "missing-report"}
    )
    assert listing.status_code == 404

    photo = _upload(client, b"patch")
    pid = photo.json()[0]["id"]
    bad_patch = client.patch(
        f"/api/v1/projects/p1/photos/{pid}", json={"report_id": "missing-report"}
    )
    assert bad_patch.status_code == 404
    assert client.get(f"/api/v1/projects/p1/photos/{pid}/original").status_code == 200


def test_photo_work_item_must_belong_to_project(client):
    bad = _upload(client, b"x", work_item_ids="w-other")
    assert bad.status_code == 404

    good = _upload(client, b"y", work_item_ids="w1")
    assert good.status_code == 201
    assert good.json()[0]["work_item_ids"] == ["w1"]

    pid = good.json()[0]["id"]
    patched = client.patch(
        f"/api/v1/projects/p1/photos/{pid}", json={"work_item_ids": []}
    )
    assert patched.status_code == 200
    assert patched.json()["work_item_ids"] == []

    linked = client.patch(
        f"/api/v1/projects/p1/photos/{pid}", json={"work_item_ids": ["w1"]}
    )
    assert linked.status_code == 200
    assert linked.json()["work_item_ids"] == ["w1"]
    cleared = client.patch(
        f"/api/v1/projects/p1/photos/{pid}", json={"work_item_ids": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["work_item_ids"] == []


def test_photo_location_component_stage_metadata_and_filters(client):
    first = _upload(
        client,
        b"photo-one",
        filename="one.jpg",
        location="Trụ T1",
        component="Bê tông",
        stage="during",
    )
    assert first.status_code == 201, first.text
    photo = first.json()[0]
    assert photo["location"] == "Trụ T1"
    assert photo["component"] == "Bê tông"
    assert photo["stage"] == "during"

    second = _upload(
        client,
        b"photo-two",
        filename="two.jpg",
        location="Trụ T2",
        component="Ván khuôn",
        stage="before",
    )
    assert second.status_code == 201, second.text

    by_location = client.get(
        "/api/v1/projects/p1/photos", params={"location": "Trụ T1"}
    )
    assert [item["id"] for item in by_location.json()] == [photo["id"]]

    by_component = client.get(
        "/api/v1/projects/p1/photos", params={"component": "Ván khuôn"}
    )
    assert [item["id"] for item in by_component.json()] == [second.json()[0]["id"]]

    by_stage = client.get("/api/v1/projects/p1/photos", params={"stage": "before"})
    assert [item["id"] for item in by_stage.json()] == [second.json()[0]["id"]]

    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    by_date = client.get("/api/v1/projects/p1/photos", params={"date": today})
    assert {item["id"] for item in by_date.json()} == {
        photo["id"],
        second.json()[0]["id"],
    }
    none_on_other_date = client.get(
        "/api/v1/projects/p1/photos", params={"date": "2000-01-01"}
    )
    assert none_on_other_date.json() == []

    # Other project sees nothing, even with matching filters.
    assert (
        client.get(
            "/api/v1/projects/p2/photos", params={"location": "Trụ T1"}
        ).json()
        == []
    )

    patched = client.patch(
        f"/api/v1/projects/p1/photos/{photo['id']}",
        json={"location": "Trụ T3", "component": None, "stage": "after"},
    )
    assert patched.status_code == 200
    assert patched.json()["location"] == "Trụ T3"
    assert patched.json()["component"] is None
    assert patched.json()["stage"] == "after"
    # Original bytes remain unchanged after metadata edits.
    assert (
        client.get(f"/api/v1/projects/p1/photos/{photo['id']}/original").content
        == b"photo-one"
    )


def test_non_image_upload_rejected_and_original_not_active_content(client):
    r = client.post(
        "/api/v1/projects/p1/photos",
        files=[("files", ("x.html", io.BytesIO(b"<script>alert(1)</script>"), "text/html"))],
    )
    assert r.status_code == 422

    svg = client.post(
        "/api/v1/projects/p1/photos",
        files=[
            (
                "files",
                ("x.svg", io.BytesIO(b"<svg xmlns='http://www.w3.org/2000/svg'/>"), "image/svg+xml"),
            )
        ],
    )
    assert svg.status_code == 422

    octet = client.post(
        "/api/v1/projects/p1/photos",
        files=[
            (
                "files",
                ("photo.png", io.BytesIO(b"png-bytes"), "application/octet-stream"),
            )
        ],
    )
    assert octet.status_code == 201
    photo = octet.json()[0]
    assert photo["mime_type"] == "image/png"


def test_photo_filter_by_work_item_and_project_isolation(client):
    linked = _upload(client, b"linked-photo", work_item_ids="w1")
    assert linked.status_code == 201
    linked_id = linked.json()[0]["id"]
    _upload(client, b"unlinked-photo")

    filtered = client.get(
        "/api/v1/projects/p1/photos", params={"work_item_id": "w1"}
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [linked_id]

    # The same work-item filter cannot leak a p1 photo through p2.
    other_project = client.get(
        "/api/v1/projects/p2/photos", params={"work_item_id": "w1"}
    )
    assert other_project.status_code == 200
    assert other_project.json() == []

    unknown = client.get(
        "/api/v1/projects/p1/photos", params={"work_item_id": "missing"}
    )
    assert unknown.status_code == 200
    assert unknown.json() == []


def test_empty_and_oversized_photo_rejected(client, monkeypatch):
    empty = _upload(client, b"")
    assert empty.status_code == 422

    monkeypatch.setattr("app.site.service.MAX_PHOTO_BYTES", 3)
    oversized = _upload(client, b"1234")
    assert oversized.status_code == 413


def test_client_upload_ids_count_must_match_files(client):
    r = client.post(
        "/api/v1/projects/p1/photos",
        files=[("files", ("a.png", io.BytesIO(b"a"), "image/png"))],
        data={"client_upload_ids": "a,b"},
    )
    assert r.status_code == 422


def test_exif_capture_time_is_interpreted_as_local_time():
    value = _exif_datetime_to_utc("2026:11:11 09:30:00")
    assert value == datetime(2026, 11, 11, 2, 30, tzinfo=timezone.utc)
    assert _exif_datetime_to_utc("not-a-date") is None
    assert _dms_to_deg((10, 30, 0), "S") == -10.5
    assert _dms_to_deg((106, 45, 0), "E") == pytest.approx(106.75)


def test_exif_metadata_extracted_without_claiming_gps_confirmation(client):
    from PIL import Image

    image = Image.new("RGB", (4, 4), color=(255, 0, 0))
    exif = Image.Exif()
    exif[271] = "TestMake"
    exif[272] = "TestModel"
    exif[36867] = "2026:11:11 09:30:00"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    r = _upload(client, buffer.getvalue(), filename="exif.jpg")
    assert r.status_code == 201, r.text
    photo = r.json()[0]
    assert photo["device"] == "TestMake TestModel"
    assert photo["capture_time"] is not None
    assert photo["gps_confirmed"] is False
    assert photo["gps_source"] is None


def test_original_path_outside_storage_is_refused():
    fake = SimpleNamespace(original_path="/etc/passwd")
    with pytest.raises(ProjectResourceNotFound):
        resolve_photo_path(fake)
