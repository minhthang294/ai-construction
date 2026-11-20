"""Reviewed journal snapshots and frozen exports, using temporary storage only."""

import io
import json
import zipfile
from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from app.acceptance.models import AcceptanceRecord, AcceptanceRequest
from app.core.component_models import (
    ComponentStage,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)


def _seed_component(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    with Session() as db:
        zone = StructureZone(
            id="jz1", project_id="p1", name="Cầu chính", name_key="cầu chính"
        )
        db.add(zone)
        db.flush()
        segment = Segment(id="js1", zone_id="jz1", number=1, source_code="PD1")
        db.add(segment)
        db.flush()
        db.add(
            StructuralComponent(
                id="jc1",
                project_id="p1",
                segment_id="js1",
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
            RepairScope(
                id="jsc1",
                component_id="jc1",
                kind="DESIGN_SCOPE",
                verification="VERIFIED",
            )
        )
        db.add(
            StageDefinition(
                id="jsd1",
                project_id="p1",
                component_type="pile",
                code="PILE-REPAIR",
                name="Sửa chữa cọc",
                position=1,
            )
        )
        db.flush()
        db.add(
            ComponentStage(
                id="jst1",
                component_id="jc1",
                stage_definition_id="jsd1",
                repair_scope_id="jsc1",
                created_by="test-user",
            )
        )
        db.commit()
    return Session


def _reviewed_report(client, date_value="2026-11-18"):
    response = client.put(
        f"/api/v1/projects/p1/daily-reports/{date_value}",
        json={
            "status": "reviewed",
            "notes": "Ghi chú ngày",
            "site_notes": {
                "weather": "Nắng",
                "difficulties": "Thiếu nước",
                "safety": "Đủ PPE",
            },
            "manpower": [
                {"group_name": "Công nhân", "count": 3},
                {"group_name": "Kỹ thuật", "count": None},
            ],
            "work_logs": [
                {"work_name": "Đục bê tông", "location": "Cọc I36"}
            ],
            "next_day_plans": [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _upload(client, data, filename, **form):
    return client.post(
        "/api/v1/projects/p1/photos",
        files=[("files", (filename, io.BytesIO(data), "image/png"))],
        data=form,
    )


def _preview(client, date_value="2026-11-18"):
    response = client.get(f"/api/v1/projects/p1/journals/{date_value}/preview")
    assert response.status_code == 200, response.text
    return response.json()


def test_snapshot_requires_reviewed_preview_and_freezes_confirmed_evidence(
    client, db_engine
):
    _seed_component(db_engine)
    draft = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-18",
        json={
            "status": "draft",
            "manpower": [],
            "work_logs": [],
            "next_day_plans": [],
        },
    ).json()
    preview = _preview(client)
    assert preview["snapshot_eligible"] is False
    assert "DAILY_REPORT_NOT_REVIEWED" in preview["blockers"]
    assert client.post(
        "/api/v1/projects/p1/journals/2026-11-18/snapshots",
        json={"reviewed": True, "preview_sha256": preview["preview_sha256"]},
    ).status_code == 409

    report = _reviewed_report(client)
    confirmed = _upload(
        client,
        b"confirmed-journal-photo",
        "evidence.png",
        report_id=report["id"],
        confirmed_caption="Ảnh cọc I36",
        category="progress",
    )
    assert confirmed.status_code == 201, confirmed.text
    photo_id = confirmed.json()[0]["id"]
    unconfirmed = _upload(
        client,
        b"unconfirmed-journal-photo",
        "omitted.png",
        report_id=report["id"],
        suggested_caption="AI only",
    )
    assert unconfirmed.status_code == 201

    event = client.post(
        "/api/v1/projects/p1/progress/bulk",
        json={
            "reviewed": True,
            "idempotency_key": "journal-1",
            "stage_definition_id": "jsd1",
            "component_ids": ["jc1"],
            "event_date": "2026-11-18",
            "status": "COMPLETED",
            "quantity": 1,
            "unit": "m3",
            "note": "Hoàn thành",
            "evidence_refs": [f"photo:{photo_id}"],
        },
    )
    assert event.status_code == 201, event.text

    preview = _preview(client)
    assert preview["snapshot_eligible"] is True
    assert preview["blockers"] == []
    assert preview["evidence_summary"]["evidence_count"] == 1
    assert preview["evidence_summary"]["omitted_evidence_count"] >= 1
    assert "Đục bê tông" in preview["preview_text"]
    assert "Nắng" in preview["preview_text"]

    assert client.post(
        "/api/v1/projects/p1/journals/2026-11-18/snapshots",
        json={"reviewed": False, "preview_sha256": preview["preview_sha256"]},
    ).status_code == 422
    assert client.post(
        "/api/v1/projects/p1/journals/2026-11-18/snapshots",
        json={"reviewed": True, "preview_sha256": "0" * 64},
    ).status_code == 409

    snapshot = client.post(
        "/api/v1/projects/p1/journals/2026-11-18/snapshots",
        json={"reviewed": True, "preview_sha256": preview["preview_sha256"]},
    )
    assert snapshot.status_code == 201, snapshot.text
    body = snapshot.json()
    assert body["sha256"]
    assert body["evidence_count"] == 1
    assert body["omitted_evidence_count"] >= 1
    assert body["acceptance_count"] == 0

    downloaded = client.get(body["download_url"])
    assert downloaded.status_code == 200
    frozen = json.loads(downloaded.content)
    assert frozen["reviewed"] is True
    assert frozen["reviewed_by"] == "test-user"
    assert frozen["date"] == "2026-11-18"
    assert frozen["preview_sha256"] == preview["preview_sha256"]
    assert [item["photo_id"] for item in frozen["evidence"]] == [photo_id]
    relative = frozen["evidence"][0]["relative_path"]
    assert relative.startswith("evidence/")

    listed = client.get("/api/v1/projects/p1/journals/2026-11-18/snapshots")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [body["id"]]


def test_exports_use_the_frozen_snapshot_and_never_invent_acceptance(
    client, db_engine
):
    _seed_component(db_engine)
    report = _reviewed_report(client)
    confirmed = _upload(
        client,
        b"zip-evidence",
        "zip.png",
        report_id=report["id"],
        confirmed_caption="Ảnh nghiệm thu",
        category="progress",
    )
    photo_id = confirmed.json()[0]["id"]
    assert client.post(
        "/api/v1/projects/p1/progress/bulk",
        json={
            "reviewed": True,
            "idempotency_key": "journal-export-1",
            "stage_definition_id": "jsd1",
            "component_ids": ["jc1"],
            "event_date": "2026-11-18",
            "status": "COMPLETED",
            "evidence_refs": [photo_id],
        },
    ).status_code == 201

    preview = _preview(client)
    snapshot = client.post(
        "/api/v1/projects/p1/journals/2026-11-18/snapshots",
        json={"reviewed": True, "preview_sha256": preview["preview_sha256"]},
    )
    assert snapshot.status_code == 201, snapshot.text
    snapshot_id = snapshot.json()["id"]

    # Live data changes after review must not leak into the frozen export.
    report_update = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-18",
        json={
            "status": "reviewed",
            "manpower": [{"group_name": "Công nhân", "count": 99}],
            "work_logs": [{"work_name": "THAY ĐỔI SAU SNAPSHOT"}],
            "next_day_plans": [],
        },
    )
    assert report_update.status_code == 200, report_update.text
    assert client.post(
        "/api/v1/projects/p1/progress/bulk",
        json={
            "reviewed": True,
            "idempotency_key": "journal-export-2",
            "stage_definition_id": "jsd1",
            "component_ids": ["jc1"],
            "event_date": "2026-11-18",
            "status": "BLOCKED",
            "evidence_refs": [],
        },
    ).status_code == 201

    exported = client.post(
        "/api/v1/projects/p1/journals/2026-11-18/exports",
        json={"snapshot_id": snapshot_id, "format": "zip"},
    )
    assert exported.status_code == 201, exported.text
    export_body = exported.json()
    assert export_body["snapshot_sha256"] == snapshot.json()["sha256"]
    archive_bytes = client.get(export_body["download_url"])
    assert archive_bytes.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive_bytes.content)) as archive:
        names = set(archive.namelist())
        assert "snapshot.json" in names
        assert "journal.txt" in names
        assert "journal.pdf" in names
        assert "journal.docx" in names
        assert any(name.startswith("evidence/") for name in names)
        text = archive.read("journal.txt").decode("utf-8")
        frozen = json.loads(archive.read("snapshot.json"))
    assert "Đục bê tông" in text
    assert "THAY ĐỔI SAU SNAPSHOT" not in text
    assert "BLOCKED" not in text
    assert "Ảnh nghiệm thu" in text
    assert "Chưa có BBNT đã xác nhận trong ngày" in text
    assert frozen["evidence"][0]["photo_id"] == photo_id
    assert frozen["acceptance_events"] == []

    pdf = client.post(
        "/api/v1/projects/p1/journals/2026-11-18/exports",
        json={"snapshot_id": snapshot_id, "format": "pdf"},
    )
    docx = client.post(
        "/api/v1/projects/p1/journals/2026-11-18/exports",
        json={"snapshot_id": snapshot_id, "format": "docx"},
    )
    assert pdf.status_code == 201, pdf.text
    assert docx.status_code == 201, docx.text
    assert client.get(pdf.json()["download_url"]).content.startswith(b"%PDF")
    assert client.get(docx.json()["download_url"]).content.startswith(b"PK")

    history = client.get("/api/v1/projects/p1/journals/2026-11-18/exports")
    assert history.status_code == 200
    assert len(history.json()) == 3
    assert client.post(
        "/api/v1/projects/other/journals/2026-11-18/exports",
        json={"snapshot_id": snapshot_id, "format": "pdf"},
    ).status_code == 404


def test_confirmed_bbnt_is_listed_but_draft_is_never_used(client, db_engine):
    _seed_component(db_engine)
    _reviewed_report(client)
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    with Session() as db:
        db.add_all(
            [
                AcceptanceRequest(
                    id="jreq-draft",
                    project_id="p1",
                    number="YC-DRAFT",
                    status="draft",
                ),
                AcceptanceRequest(
                    id="jreq-ok",
                    project_id="p1",
                    number="YC-OK",
                    status="confirmed",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                AcceptanceRecord(
                    id="jrec-draft",
                    project_id="p1",
                    request_id="jreq-draft",
                    number="BB-DRAFT",
                    status="draft",
                    result=None,
                ),
                AcceptanceRecord(
                    id="jrec-ok",
                    project_id="p1",
                    request_id="jreq-ok",
                    number="BB-OK",
                    status="confirmed",
                    result="approved",
                    confirmed_at=datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    preview = _preview(client)
    assert [item["number"] for item in preview["acceptance_events"]] == ["BB-OK"]
    assert preview["acceptance_count"] == 1
    snapshot = client.post(
        "/api/v1/projects/p1/journals/2026-11-18/snapshots",
        json={"reviewed": True, "preview_sha256": preview["preview_sha256"]},
    )
    assert snapshot.status_code == 201, snapshot.text
    exported = client.post(
        "/api/v1/projects/p1/journals/2026-11-18/exports",
        json={"snapshot_id": snapshot.json()["id"], "format": "zip"},
    )
    assert exported.status_code == 201, exported.text
    archive_bytes = client.get(exported.json()["download_url"]).content
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        text = archive.read("journal.txt").decode("utf-8")
    assert "BB-OK" in text
    assert "BB-DRAFT" not in text
    assert "Đạt" in text
