"""Project-scoped access to reviewed drawing overlays and private sheet images."""

import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StringConstraints, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import require_project_member
from .component_models import DesignGroup, RepairScope, Segment, StructuralComponent, StructureZone
from .database import get_db
from .insights_router import _latest_events

router = APIRouter(tags=["components"])
MAP_ROOT = Path(os.environ.get(
    "DRAWING_MAP_STORAGE",
    Path(__file__).resolve().parents[3] / "data" / "storage" / "dap-maps",
))
Coordinate = Annotated[float, Field(ge=0, le=1)]
SheetId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,40}$")]
ImageName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,60}\.(jpg|jpeg)$")]


class Marker(BaseModel):
    code: str
    type: Literal["pile", "beam"]
    points: list[tuple[Coordinate, Coordinate]] = Field(min_length=1, max_length=30)
    zone: str = "Cầu chính"
    segment: int = 2
    location_review: bool = False


class Sheet(BaseModel):
    id: SheetId
    title: str
    drawing: str
    page: int = Field(gt=0)
    image: ImageName
    markers: list[Marker]


class Manifest(BaseModel):
    project_id: str
    sheets: list[Sheet]
    review: list[dict[str, str]] = Field(default_factory=list)


def _manifest(project_id: str) -> Manifest | None:
    path = MAP_ROOT / "pd2" / "manifest.json"
    if not path.is_file():
        return None
    try:
        manifest = Manifest.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise HTTPException(503, "Drawing map is not available") from exc
    return manifest if manifest.project_id == project_id else None


@router.get("/projects/{project_id}/drawing-map")
def drawing_map(project_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    manifest = _manifest(project_id)
    if manifest is None:
        return {"sheets": [], "review_count": 0, "position_review_count": 0}
    marker_keys = {(marker.type, marker.code, marker.zone, marker.segment)
                   for sheet in manifest.sheets for marker in sheet.markers}
    rows = db.execute(
        select(StructuralComponent, DesignGroup.name, StructureZone.name, Segment.number)
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .outerjoin(DesignGroup, DesignGroup.id == StructuralComponent.design_group_id)
        .where(StructuralComponent.project_id == project_id,
               StructuralComponent.verification == "VERIFIED")
    ).all()
    components: dict[tuple[str, str, str, int], list[tuple[StructuralComponent, str | None]]] = {}
    for component, group_name, zone_name, segment_number in rows:
        key = (component.type, component.canonical_code, zone_name, segment_number)
        if key in marker_keys:
            components.setdefault(key, []).append((component, group_name))
    unique_components = {key: value[0][0].id for key, value in components.items() if len(value) == 1}
    additional_ids = set(db.scalars(select(RepairScope.component_id).where(
        RepairScope.component_id.in_(list(unique_components.values())), RepairScope.kind == "ADDITIONAL_SCOPE",
        RepairScope.verification == "VERIFIED",
    )))
    latest = _latest_events(db, project_id)
    review_count = len(manifest.review)
    position_review_count = 0
    sheets = []
    for sheet in manifest.sheets:
        markers = []
        for marker in sheet.markers:
            key = (marker.type, marker.code, marker.zone, marker.segment)
            matches = components.get(key, [])
            component_id = unique_components.get(key)
            valid_shape = len(marker.points) == 1 if marker.type == "pile" else len(marker.points) >= 2
            if not component_id or not valid_shape:
                review_count += 1
                continue
            component, group_name = matches[0]
            position_review_count += int(marker.location_review)
            event = latest.get(component_id)
            markers.append({**marker.model_dump(), "component_id": component_id,
                            "design_group": group_name,
                            "origin": "ADDITIONAL_SCOPE" if component_id in additional_ids else "DESIGN_SCOPE",
                            "construction_status": event.status if event else "NOT_STARTED"})
        sheets.append({**sheet.model_dump(exclude={"image", "markers"}), "markers": markers,
                       "image_url": f"/projects/{project_id}/drawing-map/{sheet.id}/image"})
    return {"sheets": sheets, "review_count": review_count, "position_review_count": position_review_count}


@router.get("/projects/{project_id}/drawing-map/{sheet_id}/image")
def drawing_map_image(project_id: str, sheet_id: SheetId):
    require_project_member(project_id)
    manifest = _manifest(project_id)
    sheet = next((sheet for sheet in manifest.sheets if sheet.id == sheet_id), None) if manifest else None
    if sheet:
        root = (MAP_ROOT / "pd2").resolve()
        path = (root / sheet.image).resolve()
        if path.parent == root and path.is_file():
            return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
    raise HTTPException(404, "Drawing sheet not found")
