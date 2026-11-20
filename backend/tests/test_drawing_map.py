import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import drawing_map_router as drawing
from app.core.component_models import Segment, StructuralComponent, StructureZone
from app.core.database import Base


def test_private_drawing_images_require_membership_and_matching_manifest(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(drawing, "MAP_ROOT", tmp_path)
    monkeypatch.setattr(drawing, "require_project_member", seen.append)
    folder = tmp_path / "pd2"
    folder.mkdir()
    (folder / "beam.jpg").write_bytes(b"private")
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({
        "project_id": "dap",
        "sheets": [{
            "id": "beam", "title": "Drawing", "drawing": "TK-32",
            "page": 38, "image": "beam.jpg", "markers": [],
        }],
    }))
    response = drawing.drawing_map_image("dap", "beam")
    assert response.path == folder / "beam.jpg"
    assert response.headers["cache-control"] == "private, no-store"
    with pytest.raises(HTTPException, match="Drawing sheet not found"):
        drawing.drawing_map_image("other", "beam")
    assert seen == ["dap", "other"]

    manifest.write_text(manifest.read_text().replace("beam.jpg", "../beam.jpg"))
    with pytest.raises(HTTPException, match="Drawing map is not available"):
        drawing.drawing_map_image("dap", "beam")


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
    monkeypatch.setattr(drawing, "_manifest", lambda project: manifest)
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
