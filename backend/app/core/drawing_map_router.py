"""Project-scoped access to reviewed drawing overlays and private sheet images."""

import hashlib
import json
import os
import re
import threading
import unicodedata
from email.utils import formatdate
from pathlib import Path
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StringConstraints, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import require_project_member, require_project_role
from .batch_scope import batch_component_ids
from .design_parameters import display_stage_name, load_t_values
from .component_models import (ComponentMapPosition, ComponentStage, DesignGroup,
                               ProgressEvent, RepairScope, Segment, StageDefinition,
                               StructuralComponent, StructureZone)
from .database import get_db
from .insights_router import _latest_events
from .models import AuditLog, now

try:  # acceptance-owned records
    from app.acceptance.models import AcceptanceRecord, ComponentAcceptanceLink
except Exception:  # pragma: no cover - isolated core deployments
    AcceptanceRecord = ComponentAcceptanceLink = None  # type: ignore[assignment]

router = APIRouter(tags=["components"])
MAP_ROOT = Path(os.environ.get(
    "DRAWING_MAP_STORAGE",
    Path(__file__).resolve().parents[3] / "data" / "storage" / "dap-maps",
))
Coordinate = Annotated[float, Field(ge=0, le=1)]
SheetSlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,80}$")]
SheetId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_-]{1,121}$")]
ImageName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,60}\.(jpg|jpeg)$")]
KEY_PATTERN = re.compile(r"^[a-z0-9_-]{1,40}$")
IMAGE_CACHE_DIR = ".cache"
IMAGE_MAX_SIDE = 2400
IMAGE_QUALITY = 80
IMAGE_CACHE_HEADERS = {
    "Cache-Control": "private, max-age=31536000, immutable",
    "Vary": "Accept",
}
_IMAGE_VERSION_CACHE: dict[tuple[str, int, int], str] = {}
_IMAGE_VERSION_LOCK = threading.Lock()
_DERIVATIVE_LOCK = threading.Lock()
_WEBP_SUPPORTED: bool | None = None


class Marker(BaseModel):
    code: str
    type: Literal["pile", "beam"]
    points: list[tuple[Coordinate, Coordinate]] = Field(min_length=1, max_length=30)
    zone: str = "Cầu chính"
    segment: int = 2
    location_review: bool = False


class Sheet(BaseModel):
    id: SheetSlug
    title: str
    drawing: str
    page: int = Field(gt=0)
    image: ImageName
    zone: str | None = None
    segment: int | None = None
    markers: list[Marker]


class Manifest(BaseModel):
    project_id: str
    sheets: list[Sheet]
    review: list[dict[str, str]] = Field(default_factory=list)


class MapPositionIn(BaseModel):
    sheet_id: SheetId
    points: list[tuple[Coordinate, Coordinate]] = Field(min_length=1, max_length=30)
    note: str | None = Field(default=None, max_length=2000)


def _norm(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def _manifest_entries(project_id: str) -> list[tuple[str, Manifest]]:
    if not MAP_ROOT.is_dir():
        return []
    entries = []
    for folder in sorted(MAP_ROOT.iterdir()):
        if (
            not folder.is_dir()
            or folder.name == "expansion"
            or not KEY_PATTERN.fullmatch(folder.name)
        ):
            continue
        path = folder / "manifest.json"
        if not path.is_file():
            continue
        try:
            manifest = Manifest.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as exc:
            raise HTTPException(503, "Drawing map is not available") from exc
        if manifest.project_id == project_id:
            entries.append((folder.name, manifest))
    return entries


def _manifest(project_id: str) -> Manifest | None:
    """Compatibility helper for callers that only need the first manifest."""
    entries = _manifest_entries(project_id)
    return entries[0][1] if entries else None


def _find_sheet(project_id: str, public_id: str) -> tuple[str, Sheet] | None:
    for key, manifest in _manifest_entries(project_id):
        for sheet in manifest.sheets:
            if f"{key}-{sheet.id}" == public_id:
                return key, sheet
    return None


def _image_version(path: Path) -> str:
    """Short version from file metadata; cached until mtime/size changes."""
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    with _IMAGE_VERSION_LOCK:
        cached = _IMAGE_VERSION_CACHE.get(key)
        if cached is not None:
            return cached
        version = hashlib.sha256(
            f"{stat.st_mtime_ns}:{stat.st_size}".encode()
        ).hexdigest()[:12]
        for old_key in [
            existing
            for existing in _IMAGE_VERSION_CACHE
            if existing[0] == key[0] and existing != key
        ]:
            _IMAGE_VERSION_CACHE.pop(old_key, None)
        _IMAGE_VERSION_CACHE[key] = version
        return version


def _safe_image_version(path: Path) -> str | None:
    try:
        return _image_version(path)
    except OSError:
        return None


def _webp_supported() -> bool:
    global _WEBP_SUPPORTED
    if _WEBP_SUPPORTED is None:
        try:
            from PIL import features

            _WEBP_SUPPORTED = bool(features.check("webp"))
        except Exception:  # pragma: no cover - Pillow is a deployment dependency
            _WEBP_SUPPORTED = False
    return _WEBP_SUPPORTED


def _preferred_image_format(request: Request) -> str:
    accept = request.headers.get("accept", "").lower()
    return "WEBP" if "image/webp" in accept and _webp_supported() else "JPEG"


def _derivative_path(source: Path, version: str, image_format: str) -> Path:
    suffix = "webp" if image_format == "WEBP" else "jpg"
    return source.parent / IMAGE_CACHE_DIR / f"{source.stem}.{version}.{suffix}"


def _generate_derivative(source: Path, destination: Path, image_format: str) -> None:
    from PIL import Image, ImageOps

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened) or opened
            if image.mode not in ("RGB", "RGBA", "L"):
                image = image.convert("RGB")
            image.thumbnail(
                (IMAGE_MAX_SIDE, IMAGE_MAX_SIDE), Image.Resampling.LANCZOS
            )
            if image_format == "WEBP":
                image.save(temporary, "WEBP", quality=IMAGE_QUALITY, method=4)
            else:
                if image.mode != "RGB":
                    image = image.convert("RGB")
                image.save(
                    temporary,
                    "JPEG",
                    quality=IMAGE_QUALITY,
                    optimize=True,
                    progressive=True,
                )
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _ensure_derivative(source: Path, version: str, image_format: str) -> Path:
    destination = _derivative_path(source, version, image_format)
    if destination.is_file():
        return destination
    with _DERIVATIVE_LOCK:
        if not destination.is_file():
            _generate_derivative(source, destination, image_format)
            try:
                for stale in destination.parent.glob(
                    f"{source.stem}.*{destination.suffix}"
                ):
                    if stale != destination and stale.is_file():
                        stale.unlink()
            except OSError:
                pass
    return destination


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    for candidate in if_none_match.split(","):
        value = candidate.strip()
        if value == "*" or value == etag or value.removeprefix("W/") == etag:
            return True
    return False


def _image_headers(version: str, variant: str, modified: float) -> dict[str, str]:
    return {
        **IMAGE_CACHE_HEADERS,
        "ETag": f'"{version}-{variant}"',
        "Last-Modified": formatdate(modified, usegmt=True),
    }


def _serve_sheet_image(
    request: Request, source: Path, full: bool
) -> FileResponse | Response:
    version = _image_version(source)
    if full:
        served = source
        variant = "full"
        media_type = "image/jpeg"
    else:
        image_format = _preferred_image_format(request)
        try:
            served = _ensure_derivative(source, version, image_format)
        except Exception:
            if image_format == "WEBP":
                try:
                    image_format = "JPEG"
                    served = _ensure_derivative(source, version, image_format)
                except Exception:
                    served = source
                    image_format = "SOURCE"
            else:
                served = source
                image_format = "SOURCE"
        variant = image_format.lower()
        media_type = "image/webp" if image_format == "WEBP" else "image/jpeg"
    headers = _image_headers(version, variant, source.stat().st_mtime)
    if _etag_matches(request.headers.get("if-none-match"), headers["ETag"]):
        return Response(status_code=304, headers=headers)
    return FileResponse(served, media_type=media_type, headers=headers)


def _sheet_matches(
    sheet: Sheet, zone: str | None, segment: int | None
) -> bool:
    if zone:
        target = _norm(zone)
        values = [sheet.zone, *(marker.zone for marker in sheet.markers)]
        if not any(value and _norm(value) == target for value in values):
            return False
    if segment is not None:
        values = [sheet.segment, *(marker.segment for marker in sheet.markers)]
        if not any(value == segment for value in values):
            return False
    return True


def _position_data(position: ComponentMapPosition) -> dict:
    return {
        "id": position.id,
        "component_id": position.component_id,
        "sheet_id": position.sheet_id,
        "points": position.points,
        "status": position.status,
        "source": position.source,
        "note": position.note,
        "created_by": position.created_by,
        "created_at": position.created_at.isoformat(),
        "reviewed_by": position.reviewed_by,
        "reviewed_at": position.reviewed_at.isoformat() if position.reviewed_at else None,
    }


@router.get("/projects/{project_id}/drawing-map")
def drawing_map(
    project_id: str,
    db: Session = Depends(get_db),
    batch_id: str | None = None,
    zone: str | None = None,
    segment: int | None = None,
):
    require_project_member(project_id)
    entries = _manifest_entries(project_id)
    if not entries:
        return {"sheets": [], "review_count": 0, "position_review_count": 0}

    batch_ids: set[str] | None = None
    if batch_id:
        batch_ids = set(db.scalars(batch_component_ids(project_id, batch_id)))

    marker_keys = {
        (marker.type, marker.code, marker.zone, marker.segment)
        for _, manifest in entries
        for sheet in manifest.sheets
        for marker in sheet.markers
    }
    rows = db.execute(
        select(StructuralComponent, DesignGroup.name, StructureZone.name, Segment.number)
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .outerjoin(DesignGroup, DesignGroup.id == StructuralComponent.design_group_id)
        .where(
            StructuralComponent.project_id == project_id,
            StructuralComponent.verification == "VERIFIED",
        )
    ).all()
    components: dict[tuple[str, str, str, int], list[tuple[StructuralComponent, str | None]]] = {}
    for component, group_name, zone_name, segment_number in rows:
        key = (component.type, component.canonical_code, zone_name, segment_number)
        if key in marker_keys:
            components.setdefault(key, []).append((component, group_name))
    unique_components = {
        key: value[0][0].id for key, value in components.items() if len(value) == 1
    }

    all_rows = db.execute(
        select(StructuralComponent, DesignGroup.name, StructureZone.name, Segment.number)
        .join(Segment, Segment.id == StructuralComponent.segment_id)
        .join(StructureZone, StructureZone.id == Segment.zone_id)
        .outerjoin(DesignGroup, DesignGroup.id == StructuralComponent.design_group_id)
        .where(StructuralComponent.project_id == project_id)
    ).all()
    component_meta = {
        component.id: (component, group_name, zone_name, segment_number)
        for component, group_name, zone_name, segment_number in all_rows
    }
    scope_ids = set(db.scalars(select(RepairScope.component_id).where(
        RepairScope.component_id.in_(list(component_meta)),
        RepairScope.kind == "ADDITIONAL_SCOPE",
        RepairScope.verification != "REJECTED",
    ))) if component_meta else set()
    additional_ids = scope_ids | {
        component.id for component, _, _, _ in all_rows
        if component.record_origin == "ADDITIONAL"
    }
    latest = _latest_events(db, project_id)
    accepted_ids: set[str] = set()
    if (
        AcceptanceRecord is not None
        and ComponentAcceptanceLink is not None
        and component_meta
    ):
        accepted_ids = set(
            db.scalars(
                select(ComponentAcceptanceLink.component_id)
                .join(
                    AcceptanceRecord,
                    ComponentAcceptanceLink.record_id == AcceptanceRecord.id,
                )
                .where(
                    ComponentAcceptanceLink.project_id == project_id,
                    AcceptanceRecord.project_id == project_id,
                    AcceptanceRecord.status == "confirmed",
                    ComponentAcceptanceLink.component_id.in_(list(component_meta)),
                )
            )
        )
    current_work: dict[str, tuple[datetime, str, str, str]] = {}
    latest_stage: dict[str, tuple[datetime, str, str, str, str]] = {}
    if component_meta:
        stage_events = db.execute(
            select(ComponentStage.component_id, ComponentStage.id, ComponentStage.stage_definition_id, StageDefinition.name,
                   ProgressEvent.status, ProgressEvent.created_at, ProgressEvent.id)
            .join(ProgressEvent, ProgressEvent.component_stage_id == ComponentStage.id)
            .join(StageDefinition, StageDefinition.id == ComponentStage.stage_definition_id)
            .where(ComponentStage.component_id.in_(list(component_meta)))
            .where(ProgressEvent.voided_at.is_(None))
            .order_by(ProgressEvent.created_at, ProgressEvent.id)
        ).all()
        latest_by_stage = {}
        for component_id, stage_id, definition_id, name, status, created_at, event_id in stage_events:
            latest_by_stage[(component_id, stage_id)] = (definition_id, name, status, created_at, event_id)
        t_values = load_t_values(db, list(component_meta))
        for (component_id, _), (definition_id, name, status, created_at, event_id) in latest_by_stage.items():
            display_name = display_stage_name(name, [t_values.get(component_id)])
            current = current_work.get(component_id)
            if status == "IN_PROGRESS" and (current is None or (created_at, event_id) > (current[0], current[1])):
                current_work[component_id] = (created_at, event_id, display_name, definition_id)
            previous = latest_stage.get(component_id)
            if previous is None or (created_at, event_id) > (previous[0], previous[1]):
                latest_stage[component_id] = (created_at, event_id, display_name, definition_id, status)

    positions = list(db.scalars(
        select(ComponentMapPosition)
        .where(ComponentMapPosition.project_id == project_id)
        .order_by(ComponentMapPosition.created_at, ComponentMapPosition.id)
    ))
    position_by_component_sheet: dict[tuple[str, str], ComponentMapPosition] = {}
    for position in positions:
        meta = component_meta.get(position.component_id)
        if meta is None:
            continue
        component, _, zone_name, segment_number = meta
        if batch_ids is not None and component.id not in batch_ids:
            continue
        if zone and _norm(zone) != _norm(zone_name):
            continue
        if segment is not None and segment != segment_number:
            continue
        position_by_component_sheet[(component.id, position.sheet_id)] = position
    used_positions: set[str] = set()

    def marker_payload(
        component: StructuralComponent,
        *,
        group_name: str | None,
        zone_name: str,
        segment_number: int,
        points: list[tuple[float, float]],
        position: ComponentMapPosition | None = None,
        location_review: bool = False,
    ) -> dict:
        event = latest.get(component.id)
        return {
            "code": component.canonical_code,
            "type": component.type,
            "points": points,
            "zone": zone_name,
            "segment": segment_number,
            "location_review": location_review,
            "component_id": component.id,
            "design_group": group_name,
            "current_work": current_work.get(component.id, (None, None, None))[2],
            "current_work_definition_id": current_work.get(component.id, (None, None, None, None))[3],
            "current_stage_name": latest_stage.get(component.id, (None, None, None))[2],
            "current_stage_definition_id": latest_stage.get(component.id, (None, None, None, None))[3],
            "last_event_date": event.event_date.isoformat() if event else None,
            "accepted": component.id in accepted_ids,
            "origin": "ADDITIONAL_SCOPE" if component.id in additional_ids else "DESIGN_SCOPE",
            "construction_status": event.status if event else "NOT_STARTED",
            "position_id": position.id if position else None,
            "position_status": position.status if position else None,
            "position_note": position.note if position else None,
        }

    review_count = sum(len(manifest.review) for _, manifest in entries)
    position_review_count = 0
    sheets = []
    known_sheet_ids = {
        f"{key}-{sheet.id}" for key, manifest in entries for sheet in manifest.sheets
    }
    for key, manifest in entries:
        for sheet in manifest.sheets:
            public_id = f"{key}-{sheet.id}"
            if not _sheet_matches(sheet, zone, segment):
                continue
            markers = []
            for marker in sheet.markers:
                marker_key = (marker.type, marker.code, marker.zone, marker.segment)
                component_id = unique_components.get(marker_key)
                if component_id and batch_ids is not None and component_id not in batch_ids:
                    continue
                if zone and _norm(zone) != _norm(marker.zone):
                    continue
                if segment is not None and segment != marker.segment:
                    continue
                if not component_id:
                    review_count += 1
                    continue
                meta = component_meta[component_id]
                component, group_name, zone_name, segment_number = meta
                if zone and _norm(zone) != _norm(zone_name):
                    continue
                if segment is not None and segment != segment_number:
                    continue
                valid_shape = len(marker.points) == 1 if marker.type == "pile" else len(marker.points) >= 2
                if not valid_shape:
                    review_count += 1
                    continue
                position = position_by_component_sheet.get((component_id, public_id))
                points = (
                    [[float(point[0]), float(point[1])] for point in position.points]
                    if position else [[float(point[0]), float(point[1])] for point in marker.points]
                )
                if position:
                    used_positions.add(position.id)
                    position_review_count += int(position.status == "DRAFT")
                else:
                    position_review_count += int(marker.location_review)
                markers.append(marker_payload(
                    component,
                    group_name=group_name,
                    zone_name=zone_name,
                    segment_number=segment_number,
                    points=points,
                    position=position,
                    location_review=marker.location_review,
                ))

            for position in positions:
                if position.id in used_positions or position.sheet_id != public_id:
                    continue
                meta = component_meta.get(position.component_id)
                if meta is None:
                    continue
                component, group_name, zone_name, segment_number = meta
                if batch_ids is not None and component.id not in batch_ids:
                    continue
                if zone and _norm(zone) != _norm(zone_name):
                    continue
                if segment is not None and segment != segment_number:
                    continue
                valid_shape = len(position.points) == 1 if component.type == "pile" else len(position.points) >= 2
                if not valid_shape:
                    continue
                used_positions.add(position.id)
                position_review_count += int(position.status == "DRAFT")
                markers.append(marker_payload(
                    component,
                    group_name=group_name,
                    zone_name=zone_name,
                    segment_number=segment_number,
                    points=[[float(point[0]), float(point[1])] for point in position.points],
                    position=position,
                ))

            if (batch_ids is not None or zone or segment is not None) and not markers:
                continue
            image_version = _safe_image_version(MAP_ROOT / key / sheet.image)
            image_url = f"/projects/{project_id}/drawing-map/{public_id}/image"
            if image_version:
                image_url += f"?v={image_version}"
            sheets.append({
                **sheet.model_dump(exclude={"image", "markers", "id", "zone", "segment"}),
                "id": public_id,
                "zone": sheet.zone,
                "segment": sheet.segment,
                "markers": markers,
                "image_url": image_url,
            })
    review_count += sum(
        1 for position in positions
        if position.sheet_id not in known_sheet_ids
    )
    return {
        "sheets": sheets,
        "review_count": review_count,
        "position_review_count": position_review_count,
    }


@router.put("/projects/{project_id}/components/{component_id}/map-position")
def save_map_position(
    project_id: str,
    component_id: str,
    payload: MapPositionIn,
    db: Session = Depends(get_db),
):
    actor = require_project_role(project_id, {"project_manager", "engineer"})
    component = db.scalar(select(StructuralComponent).where(
        StructuralComponent.id == component_id,
        StructuralComponent.project_id == project_id,
    ))
    if component is None:
        raise HTTPException(404, "Component not found")
    if _find_sheet(project_id, payload.sheet_id) is None:
        raise HTTPException(404, "Drawing sheet not found")
    points = [[float(x), float(y)] for x, y in payload.points]
    if component.type == "pile" and len(points) != 1:
        raise HTTPException(422, "A pile position needs exactly one point")
    if component.type == "beam" and len(points) < 2:
        raise HTTPException(422, "A beam position needs at least two points")
    position = db.scalar(select(ComponentMapPosition).where(
        ComponentMapPosition.component_id == component.id,
        ComponentMapPosition.sheet_id == payload.sheet_id,
    ))
    before = _position_data(position) if position else None
    if position is None:
        position = ComponentMapPosition(
            project_id=project_id,
            component_id=component.id,
            sheet_id=payload.sheet_id,
            points=points,
            status="DRAFT",
            source="manual",
            created_by=actor.id,
            note=(payload.note or "").strip() or None,
        )
        db.add(position)
    else:
        position.points = points
        position.note = (payload.note or "").strip() or None
        position.status = "DRAFT"
        position.reviewed_by = None
        position.reviewed_at = None
    db.flush()
    db.add(AuditLog(
        project_id=project_id,
        actor_id=actor.id,
        action="component_map_position_saved",
        entity="ComponentMapPosition",
        entity_id=position.id,
        detail=json.dumps({
            "component_id": component.id,
            "sheet_id": payload.sheet_id,
            "before": before,
            "points": points,
            "status": "DRAFT",
        }),
    ))
    db.commit()
    db.refresh(position)
    return _position_data(position)


@router.post("/projects/{project_id}/components/{component_id}/map-position/review")
def review_map_position(
    project_id: str,
    component_id: str,
    db: Session = Depends(get_db),
    sheet_id: SheetId | None = None,
):
    actor = require_project_role(project_id, {"project_manager"})
    query = (
        select(ComponentMapPosition)
        .join(StructuralComponent, ComponentMapPosition.component_id == StructuralComponent.id)
        .where(
            ComponentMapPosition.project_id == project_id,
            ComponentMapPosition.component_id == component_id,
            StructuralComponent.project_id == project_id,
        )
        .order_by(ComponentMapPosition.created_at.desc())
    )
    if sheet_id:
        query = query.where(ComponentMapPosition.sheet_id == sheet_id)
    position = db.scalar(query)
    if position is None:
        raise HTTPException(404, "Map position not found")
    if position.status == "REVIEWED":
        raise HTTPException(409, "Map position already reviewed")
    position.status = "REVIEWED"
    position.reviewed_by = actor.id
    position.reviewed_at = now()
    db.add(AuditLog(
        project_id=project_id,
        actor_id=actor.id,
        action="component_map_position_reviewed",
        entity="ComponentMapPosition",
        entity_id=position.id,
        detail=json.dumps({
            "component_id": position.component_id,
            "sheet_id": position.sheet_id,
        }),
    ))
    db.commit()
    db.refresh(position)
    return _position_data(position)


@router.get("/projects/{project_id}/drawing-map/{sheet_id}/image")
def drawing_map_image(
    project_id: str,
    sheet_id: SheetId,
    request: Request,
    full: bool = False,
):
    require_project_member(project_id)
    found = _find_sheet(project_id, sheet_id)
    if found:
        key, sheet = found
        root = (MAP_ROOT / key).resolve()
        path = (root / sheet.image).resolve()
        if path.parent == root and path.is_file():
            return _serve_sheet_image(request, path, full)
    raise HTTPException(404, "Drawing sheet not found")
