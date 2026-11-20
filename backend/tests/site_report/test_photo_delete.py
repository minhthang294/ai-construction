"""Project-scoped photo deletion and evidence retention."""

import io
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.acceptance.models import (
    AcceptanceChecklist,
    AcceptanceRecord,
    AcceptanceRequest,
)
from app.core.component_models import ProgressEvent, Segment, StructuralComponent, StructureZone
from app.core.models import AuditLog
from app.site.models import GeneratedDocument, PhotoWorkItemLink, SitePhoto
from app.site.service import STORAGE_ROOT, sha256_bytes


def _upload(client, data=b"photo-bytes", filename="photo.png", **form):
    return client.post(
        "/api/v1/projects/p1/photos",
        files=[("files", (filename, io.BytesIO(data), "image/png"))],
        data=form,
    )


def _session(db_engine):
    return sessionmaker(bind=db_engine, expire_on_commit=False)


def _photo_path(db_engine, photo_id):
    Session = _session(db_engine)
    with Session() as db:
        photo = db.get(SitePhoto, photo_id)
        assert photo is not None
        return Path(photo.original_path)


def _seed_progress_event(db_engine, photo_id, event_id="evt-1", ref=None):
    Session = _session(db_engine)
    with Session() as db:
        db.add(StructureZone(id="pdz", project_id="p1", name="Khu A", name_key="khu a"))
        db.flush()
        db.add(Segment(id="pds", zone_id="pdz", number=1, source_code="PD1"))
        db.flush()
        db.add(
            StructuralComponent(
                id="pdc",
                project_id="p1",
                segment_id="pds",
                type="pile",
                raw_code="I36",
                canonical_code="I36",
                verification="VERIFIED",
                record_origin="SEED_IMPORT",
                created_by="test-user",
            )
        )
        db.flush()
        db.add(
            ProgressEvent(
                id=event_id,
                component_id="pdc",
                component_stage_id="missing-stage",
                event_date=date(2026, 11, 18),
                status="COMPLETED",
                evidence_refs=json.dumps([ref or f"photo:{photo_id}"]),
                created_by="test-user",
            )
        )
        db.commit()


def test_delete_unlinked_photo_removes_file_links_and_writes_audit(client, db_engine):
    uploaded = _upload(client, b"delete-me", work_item_ids="w1")
    assert uploaded.status_code == 201, uploaded.text
    photo = uploaded.json()[0]
    path = _photo_path(db_engine, photo["id"])
    assert path.is_file()

    response = client.delete(f"/api/v1/projects/p1/photos/{photo['id']}")
    assert response.status_code == 204, response.text
    assert response.content == b""

    assert client.get(f"/api/v1/projects/p1/photos/{photo['id']}/original").status_code == 404
    assert client.get("/api/v1/projects/p1/photos").json() == []
    assert not path.exists()

    Session = _session(db_engine)
    with Session() as db:
        assert db.get(SitePhoto, photo["id"]) is None
        assert db.scalar(
            select(PhotoWorkItemLink).where(PhotoWorkItemLink.photo_id == photo["id"])
        ) is None
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.project_id == "p1",
                AuditLog.action == "delete_photo",
                AuditLog.entity_id == photo["id"],
            )
        )
        assert audit is not None
        detail = json.loads(audit.detail)
        assert detail["sha256"] == photo["sha256"]
        assert detail["file_removed"] is True

    # Deleting again is a clean 404, not a server error.
    assert client.delete(f"/api/v1/projects/p1/photos/{photo['id']}").status_code == 404


def test_delete_photo_is_project_scoped(client, db_engine):
    uploaded = _upload(client, b"scope")
    photo_id = uploaded.json()[0]["id"]
    path = _photo_path(db_engine, photo_id)

    response = client.delete(f"/api/v1/projects/p2/photos/{photo_id}")
    assert response.status_code == 404
    assert client.get(f"/api/v1/projects/p1/photos/{photo_id}/original").status_code == 200
    assert path.is_file()

    Session = _session(db_engine)
    with Session() as db:
        assert db.get(SitePhoto, photo_id) is not None


def test_delete_photo_blocked_by_progress_evidence(client, db_engine):
    uploaded = _upload(client, category="progress")
    photo = uploaded.json()[0]
    path = _photo_path(db_engine, photo["id"])
    _seed_progress_event(db_engine, photo["id"])

    response = client.delete(f"/api/v1/projects/p1/photos/{photo['id']}")
    assert response.status_code == 409
    assert "progress event" in response.json()["detail"]
    assert path.is_file()
    assert (
        client.get(f"/api/v1/projects/p1/photos/{photo['id']}/original").status_code
        == 200
    )

    Session = _session(db_engine)
    with Session() as db:
        assert db.get(SitePhoto, photo["id"]) is not None
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "delete_photo_blocked",
                AuditLog.entity_id == photo["id"],
            )
        )
        assert audit is not None
        assert "progress event" in audit.detail


def test_delete_photo_blocked_when_bare_reference_used_in_progress(client, db_engine):
    uploaded = _upload(client, category="progress")
    photo = uploaded.json()[0]
    _seed_progress_event(db_engine, photo["id"], ref=photo["id"])

    response = client.delete(f"/api/v1/projects/p1/photos/{photo['id']}")
    assert response.status_code == 409
    assert "progress event" in response.json()["detail"]


def test_delete_photo_blocked_by_reviewed_daily_report_only(client, db_engine):
    report = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-18",
        json={
            "status": "reviewed",
            "manpower": [],
            "work_logs": [],
            "next_day_plans": [],
        },
    ).json()
    uploaded = _upload(client, b"report-evidence", report_id=report["id"], category="progress")
    photo_id = uploaded.json()[0]["id"]
    path = _photo_path(db_engine, photo_id)

    response = client.delete(f"/api/v1/projects/p1/photos/{photo_id}")
    assert response.status_code == 409
    assert "daily report" in response.json()["detail"]
    assert path.is_file()

    # A draft report no longer freezes the photo as evidence.
    assert (
        client.put(
            "/api/v1/projects/p1/daily-reports/2026-11-18",
            json={
                "status": "draft",
                "manpower": [],
                "work_logs": [],
                "next_day_plans": [],
            },
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/projects/p1/photos/{photo_id}").status_code == 204


def test_delete_photo_blocked_by_finalized_journal_snapshot(client, db_engine):
    uploaded = _upload(client, b"journal-evidence", category="progress")
    photo = uploaded.json()[0]
    path = _photo_path(db_engine, photo["id"])

    snapshot_dir = (
        STORAGE_ROOT / "projects" / "p1" / "journals" / "2026-11-18" / "snap-1"
    )
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / "snapshot.json"
    snapshot = {
        "project_id": "p1",
        "date": "2026-11-18",
        "reviewed": True,
        "evidence": [{"photo_id": photo["id"], "sha256": photo["sha256"]}],
    }
    data = json.dumps(snapshot).encode("utf-8")
    snapshot_path.write_bytes(data)

    Session = _session(db_engine)
    with Session() as db:
        db.add(
            GeneratedDocument(
                id="snap-1",
                project_id="p1",
                kind="journal_snapshot",
                path=str(snapshot_path),
                sha256=sha256_bytes(data),
                format="json",
                report_date=date(2026, 11, 18),
                metadata_json=json.dumps({"evidence_count": 1}),
            )
        )
        db.commit()

    response = client.delete(f"/api/v1/projects/p1/photos/{photo['id']}")
    assert response.status_code == 409
    assert "journal snapshot" in response.json()["detail"]
    assert path.is_file()

    # The frozen snapshot remains self-contained.
    assert json.loads(snapshot_path.read_bytes())["evidence"][0]["photo_id"] == photo["id"]


def test_delete_photo_blocked_by_acceptance_checklist_and_request(client, db_engine):
    report = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-19",
        json={
            "status": "draft",
            "manpower": [],
            "work_logs": [],
            "next_day_plans": [],
        },
    ).json()
    uploaded = _upload(
        client,
        b"acceptance-evidence",
        report_id=report["id"],
        confirmed_caption="Ảnh nghiệm thu",
    )
    photo = uploaded.json()[0]
    _photo_path(db_engine, photo["id"])

    Session = _session(db_engine)
    with Session() as db:
        db.add(
            AcceptanceRequest(
                id="areq-1",
                project_id="p1",
                number="YC-1",
                status="draft",
                daily_report_id=report["id"],
            )
        )
        db.flush()
        db.add(
            AcceptanceRecord(
                id="arec-1",
                project_id="p1",
                request_id="areq-1",
                number="BB-1",
                status="draft",
            )
        )
        db.flush()
        db.add(
            AcceptanceChecklist(
                id="achk-1",
                project_id="p1",
                record_id="arec-1",
                item="Kiểm tra bề mặt",
                state="unconfirmed",
                evidence_refs=json.dumps([f"photo:{photo['id']}"]),
            )
        )
        db.commit()

    response = client.delete(f"/api/v1/projects/p1/photos/{photo['id']}")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "acceptance checklist" in detail
    assert "acceptance request" in detail


def test_delete_photo_refuses_file_outside_storage(client, db_engine, tmp_path):
    uploaded = _upload(client, b"unsafe")
    photo_id = uploaded.json()[0]["id"]
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"keep-me")

    Session = _session(db_engine)
    with Session() as db:
        db.get(SitePhoto, photo_id).original_path = str(outside)
        db.commit()

    response = client.delete(f"/api/v1/projects/p1/photos/{photo_id}")
    assert response.status_code == 404
    assert outside.read_bytes() == b"keep-me"
    with Session() as db:
        assert db.get(SitePhoto, photo_id) is not None


def test_delete_photo_cleans_metadata_when_file_is_already_missing(client, db_engine):
    uploaded = _upload(client, b"already-gone")
    photo_id = uploaded.json()[0]["id"]
    path = _photo_path(db_engine, photo_id)
    path.unlink()

    response = client.delete(f"/api/v1/projects/p1/photos/{photo_id}")
    assert response.status_code == 204
    assert client.get("/api/v1/projects/p1/photos").json() == []


def test_delete_photo_file_failure_keeps_photo_and_audits(
    client, db_engine, monkeypatch
):
    uploaded = _upload(client, b"locked-file")
    photo_id = uploaded.json()[0]["id"]
    path = _photo_path(db_engine, photo_id)
    original_unlink = Path.unlink

    def fail_target(self, *args, **kwargs):
        if self == path:
            raise PermissionError("file is locked")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_target)

    response = client.delete(f"/api/v1/projects/p1/photos/{photo_id}")
    assert response.status_code == 500
    assert path.is_file()

    Session = _session(db_engine)
    with Session() as db:
        assert db.get(SitePhoto, photo_id) is not None
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "delete_photo_failed",
                AuditLog.entity_id == photo_id,
            )
        )
        assert audit is not None
        assert json.loads(audit.detail)["reason"] == "PermissionError"
