import json
import os
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core import drawing_map_router as drawing
from app.core.component_models import (ComponentDesignParameter, ComponentMapPosition,
                                       ComponentStage, ConstructionBatch,
                                       ConstructionBatchComponent, ProgressEvent,
                                       RepairScope, StageDefinition, Segment,
                                       StructuralComponent, StructureZone)
from app.core.database import Base
from app.acceptance.models import AcceptanceRecord, AcceptanceRequest, ComponentAcceptanceLink
from app.core.models import AuditLog


def _request(headers: dict[str, str] | None = None) -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (key.lower().encode(), value.encode())
            for key, value in (headers or {}).items()
        ],
    })


def _write_jpeg(path, size=(3000, 2000)) -> None:
    Image.effect_noise(size, 100).convert("RGB").save(path, "JPEG", quality=95)


def test_private_drawing_images_require_membership_and_matching_manifest(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(drawing, "MAP_ROOT", tmp_path)
    monkeypatch.setattr(drawing, "require_project_member", seen.append)
    folder = tmp_path / "pd2"
    folder.mkdir()
    original = folder / "beam.jpg"
    _write_jpeg(original)
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({
        "project_id": "dap",
        "sheets": [{
            "id": "beam", "title": "Drawing", "drawing": "TK-32",
            "page": 38, "image": "beam.jpg", "markers": [],
        }],
    }))
    calls = []
    generate = drawing._generate_derivative

    def tracked(*args):
        calls.append(args)
        return generate(*args)

    monkeypatch.setattr(drawing, "_generate_derivative", tracked)
    response = drawing.drawing_map_image("dap", "pd2-beam", _request())
    assert response.path.parent == folder / ".cache"
    assert response.path.suffix == ".jpg"
    assert response.path.stat().st_size < original.stat().st_size
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert response.headers["etag"]
    assert response.headers["last-modified"]
    assert len(calls) == 1

    reused = drawing.drawing_map_image("dap", "pd2-beam", _request())
    assert reused.path == response.path
    assert len(calls) == 1

    not_modified = drawing.drawing_map_image(
        "dap", "pd2-beam", _request({"if-none-match": response.headers["etag"]})
    )
    assert not_modified.status_code == 304
    assert not_modified.headers["etag"] == response.headers["etag"]

    full = drawing.drawing_map_image("dap", "pd2-beam", _request(), full=True)
    assert full.path == original
    assert full.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert full.headers["etag"] != response.headers["etag"]

    if drawing._webp_supported():
        webp = drawing.drawing_map_image(
            "dap", "pd2-beam", _request({"accept": "image/webp"})
        )
        assert webp.media_type == "image/webp"
        assert webp.path.suffix == ".webp"

    with pytest.raises(HTTPException, match="Drawing sheet not found"):
        drawing.drawing_map_image("other", "pd2-beam", _request())
    with pytest.raises(HTTPException, match="Drawing sheet not found"):
        drawing.drawing_map_image("dap", "pd2-../../beam", _request())
    assert seen.count("dap") >= 4
    assert seen[-2:] == ["other", "dap"]

    version = drawing._image_version(original)
    os.utime(original, ns=(original.stat().st_atime_ns, original.stat().st_mtime_ns + 1_000_000))
    assert drawing._image_version(original) != version
    refreshed = drawing.drawing_map_image("dap", "pd2-beam", _request())
    assert refreshed.path != response.path
    assert len(list((folder / ".cache").glob("beam.*.jpg"))) == 1

    manifest.write_text(manifest.read_text().replace("beam.jpg", "../beam.jpg"))
    with pytest.raises(HTTPException, match="Drawing map is not available"):
        drawing.drawing_map_image("dap", "pd2-beam", _request())


def test_markers_resolve_only_verified_codes_in_the_pilot_segment(monkeypatch):
    monkeypatch.setattr(drawing, "require_project_member", lambda project: None)
    manifest = drawing.Manifest.model_validate({
        "project_id": "p",
        "sheets": [{
            "id": "sheet", "title": "Test", "drawing": "TK-32", "page": 38,
            "image": "sheet.jpg", "markers": [
                {"code": "A1", "type": "pile", "points": [[0.5, 0.5]]},
                {"code": "A2", "type": "pile", "points": [[0, 0]]},
            ],
        }],
    })
    monkeypatch.setattr(drawing, "_manifest_entries", lambda project: [("pd2", manifest)])
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(StructureZone(id="z", project_id="p", name="Cầu chính", name_key="cầu chính"))
        db.add(Segment(id="s1", zone_id="z", number=1, source_code="1"))
        db.add(Segment(id="s2", zone_id="z", number=2, source_code="2"))
        for sid, code, segment in [("ok", "A1", "s2"), ("outside", "A2", "s1")]:
            db.add(StructuralComponent(id=sid, project_id="p", segment_id=segment, type="pile",
                                       raw_code=code, canonical_code=code,
                                       verification="VERIFIED", created_by="u"))
        db.commit()
        result = drawing.drawing_map("p", db)
    assert result["review_count"] == 1
    assert [marker["component_id"] for marker in result["sheets"][0]["markers"]] == ["ok"]


def test_markers_expose_terminal_stage_last_event_and_acceptance(monkeypatch):
    monkeypatch.setattr(drawing, "require_project_member", lambda project: None)
    manifest = drawing.Manifest.model_validate({
        "project_id": "p",
        "sheets": [{
            "id": "sheet", "title": "Test", "drawing": "TK-32", "page": 38,
            "image": "sheet.jpg", "markers": [
                {"code": "A1", "type": "pile", "points": [[0.5, 0.5]]},
            ],
        }],
    })
    monkeypatch.setattr(drawing, "_manifest_entries", lambda project: [("pd2", manifest)])
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(StructureZone(id="z", project_id="p", name="Cầu chính", name_key="cau chinh"))
        db.add(Segment(id="s", zone_id="z", number=2, source_code="2"))
        db.add(StructuralComponent(id="c", project_id="p", segment_id="s", type="pile",
                                   raw_code="A1", canonical_code="A1",
                                   verification="VERIFIED", created_by="u"))
        db.add(StageDefinition(id="d", project_id="p", component_type="pile",
                               code="DUC", name="Đục bê tông om vỡ dày trung bình t",
                               position=1))
        db.add(ComponentStage(id="st", component_id="c", stage_definition_id="d",
                              repair_scope_id="scope", created_by="u"))
        db.add(ComponentDesignParameter(id="dp", project_id="p", component_id="c",
                                        name="t_cm", value=3, unit="cm", created_by="u"))
        db.add(ProgressEvent(id="e", component_id="c", component_stage_id="st",
                             event_date=date(2026, 11, 20), status="IN_PROGRESS",
                             evidence_refs="[]", created_by="u"))
        db.add(AcceptanceRequest(id="r", project_id="p", number="YC-1"))
        db.add(AcceptanceRecord(id="rec", project_id="p", request_id="r", number="BB-1",
                                status="confirmed", result="approved",
                                confirmed_at=datetime(2026, 11, 21, tzinfo=timezone.utc)))
        db.add(ComponentAcceptanceLink(project_id="p", component_id="c",
                                       record_id="rec", created_by="u"))
        db.commit()
        result = drawing.drawing_map("p", db)
    marker = result["sheets"][0]["markers"][0]
    assert marker["current_stage_name"].endswith("t = 3 cm")
    assert marker["last_event_date"] == "2026-11-20"
    assert marker["accepted"] is True


def test_multi_manifest_filters_by_batch_zone_and_segment(tmp_path, monkeypatch):
    monkeypatch.setattr(drawing, "require_project_member", lambda project: None)
    for key, marker, zone, segment in (
        ("pd2", "A1", "Cầu chính", 2),
        ("bunke", "B1", "Bunke", 1),
    ):
        folder = tmp_path / key
        folder.mkdir()
        (folder / "sheet.jpg").write_bytes(b"image")
        (folder / "manifest.json").write_text(json.dumps({
            "project_id": "p",
            "sheets": [{
                "id": "main", "title": key, "drawing": "TK-32", "page": 1,
                "image": "sheet.jpg", "zone": zone, "segment": segment,
                "markers": [{"code": marker, "type": "pile",
                             "points": [[0.5, 0.5]], "zone": zone, "segment": segment}],
            }],
        }), encoding="utf-8")
    # Expansion folders and foreign projects must be ignored.
    (tmp_path / "expansion").mkdir()
    (tmp_path / "expansion" / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(drawing, "MAP_ROOT", tmp_path)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(StructureZone(id="z1", project_id="p", name="Cầu chính", name_key="cầu chính"))
        db.add(StructureZone(id="z2", project_id="p", name="Bunke", name_key="bunke"))
        db.add(Segment(id="s1", zone_id="z1", number=2, source_code="2"))
        db.add(Segment(id="s2", zone_id="z2", number=1, source_code="1"))
        for component_id, code, segment_id in (("c1", "A1", "s1"), ("c2", "B1", "s2")):
            db.add(StructuralComponent(
                id=component_id, project_id="p", segment_id=segment_id, type="pile",
                raw_code=code, canonical_code=code, verification="VERIFIED", created_by="u",
            ))
        batch = ConstructionBatch(project_id="p", name="Both", created_by="u")
        db.add(batch)
        db.flush()
        db.add_all([
            ConstructionBatchComponent(batch_id=batch.id, component_id="c1", added_by="u"),
            ConstructionBatchComponent(batch_id=batch.id, component_id="c2", added_by="u"),
        ])
        db.commit()
        batch_id = batch.id

        both = drawing.drawing_map("p", db, batch_id=batch_id)
        assert [sheet["id"] for sheet in both["sheets"]] == ["bunke-main", "pd2-main"]
        assert all("?v=" in sheet["image_url"] for sheet in both["sheets"])
        before_version = next(
            sheet["image_url"] for sheet in both["sheets"] if sheet["id"] == "pd2-main"
        )
        target = tmp_path / "pd2" / "sheet.jpg"
        os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 1_000_000))
        after_version = next(
            sheet["image_url"]
            for sheet in drawing.drawing_map("p", db, batch_id=batch_id)["sheets"]
            if sheet["id"] == "pd2-main"
        )
        assert after_version != before_version
        only_bunke = drawing.drawing_map("p", db, zone="Bunke")
        assert [sheet["id"] for sheet in only_bunke["sheets"]] == ["bunke-main"]
        only_segment = drawing.drawing_map("p", db, segment=2)
        assert [sheet["id"] for sheet in only_segment["sheets"]] == ["pd2-main"]

        single_batch = ConstructionBatch(project_id="p", name="One", created_by="u")
        db.add(single_batch)
        db.flush()
        db.add(ConstructionBatchComponent(
            batch_id=single_batch.id, component_id="c1", added_by="u"))
        db.commit()
        one = drawing.drawing_map("p", db, batch_id=single_batch.id)
        assert [sheet["id"] for sheet in one["sheets"]] == ["pd2-main"]

    image = drawing.drawing_map_image("p", "bunke-main", _request())
    assert image.path == (tmp_path / "bunke" / "sheet.jpg").resolve()


def test_db_position_override_additional_marker_and_review(monkeypatch):
    actor = type("U", (), {"id": "u"})()
    roles_seen = []

    def fake_role(project, roles):
        roles_seen.append(set(roles))
        return actor

    monkeypatch.setattr(drawing, "require_project_member", lambda project: None)
    monkeypatch.setattr(drawing, "require_project_role", fake_role)
    manifest = drawing.Manifest.model_validate({
        "project_id": "p",
        "sheets": [{
            "id": "main", "title": "Test", "drawing": "TK-32", "page": 1,
            "image": "sheet.jpg", "zone": "Cầu chính", "segment": 2,
            "markers": [{"code": "A1", "type": "pile", "points": [[0.5, 0.5]]}],
        }],
    })
    monkeypatch.setattr(drawing, "_manifest_entries", lambda project: [("pd2", manifest)])
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(StructureZone(id="z", project_id="p", name="Cầu chính", name_key="cau chinh"))
        db.add(Segment(id="s", zone_id="z", number=2, source_code="2"))
        db.add(StructuralComponent(
            id="c1", project_id="p", segment_id="s", type="pile",
            raw_code="A1", canonical_code="A1", verification="VERIFIED", created_by="u",
        ))
        db.add(StructuralComponent(
            id="c2", project_id="p", segment_id="s", type="pile",
            raw_code="NEW1", canonical_code="NEW1", verification="NEEDS_REVIEW",
            record_origin="ADDITIONAL", created_by="u",
        ))
        db.add(RepairScope(id="scope2", component_id="c2", kind="ADDITIONAL_SCOPE",
                           verification="NEEDS_REVIEW", revision=1))
        db.commit()

        drawing.save_map_position(
            "p", "c1",
            drawing.MapPositionIn(sheet_id="pd2-main", points=[(0.1, 0.1)],
                                  note="moved"),
            db,
        )
        drawing.save_map_position(
            "p", "c2",
            drawing.MapPositionIn(sheet_id="pd2-main", points=[(0.2, 0.2)]),
            db,
        )
        body = drawing.drawing_map("p", db)
    markers = {marker["component_id"]: marker for marker in body["sheets"][0]["markers"]}
    assert markers["c1"]["points"] == [[0.1, 0.1]]
    assert markers["c1"]["position_status"] == "DRAFT"
    assert markers["c2"]["origin"] == "ADDITIONAL_SCOPE"
    assert markers["c2"]["position_status"] == "DRAFT"
    assert body["position_review_count"] == 2

    with Session(engine) as db:
        reviewed = drawing.review_map_position("p", "c2", db)
        assert reviewed["status"] == "REVIEWED"
        assert db.scalar(select(AuditLog).where(
            AuditLog.action == "component_map_position_saved")) is not None
        assert db.scalar(select(AuditLog).where(
            AuditLog.action == "component_map_position_reviewed")) is not None
        assert db.scalar(select(ComponentMapPosition).where(
            ComponentMapPosition.component_id == "c1")).status == "DRAFT"
    assert {"project_manager", "engineer"} in roles_seen
    assert roles_seen[-1] == {"project_manager"}
