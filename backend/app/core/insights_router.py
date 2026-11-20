"""Read-only project progress summary and reconciliation issues.

Counts come from verified catalog records. Construction and acceptance are
reported independently; no acceptance status is inferred from progress.
"""

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import require_project_member
from .component_models import (ComponentAlias, ProgressEvent, RepairScope, Segment,
                               StructuralComponent, StructureZone)
from .database import get_db

try:  # acceptance-owned link and record models
    from app.acceptance.models import AcceptanceRecord, ComponentAcceptanceLink
except Exception:  # pragma: no cover - isolated core deployments
    AcceptanceRecord = ComponentAcceptanceLink = None

router = APIRouter(tags=["components"])

ISSUE_TYPES = ("ACCEPTANCE_WITHOUT_PROGRESS", "WORK_WITHOUT_ACCEPTANCE", "MISSING_SOURCE",
               "UNVERIFIED_COMPONENT", "DUPLICATE_OR_AMBIGUOUS_CODE", "ACCEPTANCE_BEFORE_PROGRESS")


def _components(db: Session, project_id: str):
    return db.execute(select(StructuralComponent, Segment, StructureZone).join(
        Segment, StructuralComponent.segment_id == Segment.id).join(
        StructureZone, Segment.zone_id == StructureZone.id).where(
        StructuralComponent.project_id == project_id, StructureZone.project_id == project_id)).all()


def _latest_events(db: Session, project_id: str) -> dict[str, ProgressEvent]:
    latest: dict[str, ProgressEvent] = {}
    for event in db.scalars(select(ProgressEvent).join(
            StructuralComponent, ProgressEvent.component_id == StructuralComponent.id).where(
            StructuralComponent.project_id == project_id).order_by(
            ProgressEvent.created_at, ProgressEvent.id)):
        latest[event.component_id] = event
    return latest


def _ratio(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


@router.get("/projects/{project_id}/progress/summary")
def progress_summary(project_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    rows = _components(db, project_id)
    verified = {component.id for component, _, _ in rows if component.verification == "VERIFIED"}
    latest = _latest_events(db, project_id)
    statuses = Counter()
    for component, _, _ in rows:
        if component.id in verified:
            event = latest.get(component.id)
            statuses[event.status if event else "NOT_STARTED"] += 1
    additional = set()
    if verified:
        additional = set(db.scalars(select(RepairScope.component_id).where(
            RepairScope.kind == "ADDITIONAL_SCOPE",
            RepairScope.component_id.in_(verified))))
    linked: set[str] = set()
    confirmed: set[str] = set()
    if AcceptanceRecord is not None and verified:
        for link, record in db.execute(select(ComponentAcceptanceLink, AcceptanceRecord).outerjoin(
                AcceptanceRecord, ComponentAcceptanceLink.record_id == AcceptanceRecord.id).where(
                ComponentAcceptanceLink.project_id == project_id)):
            if link.component_id not in verified:
                continue
            linked.add(link.component_id)
            if record is not None and record.status == "confirmed":
                confirmed.add(link.component_id)
    return {
        "project_id": project_id,
        "components": {"total": len(rows), "verified": len(verified),
                       "needs_review": len(rows) - len(verified),
                       "with_additional_scope": len(additional)},
        "construction": {
            "not_started": statuses["NOT_STARTED"], "in_progress": statuses["IN_PROGRESS"],
            "completed": statuses["COMPLETED"], "blocked": statuses["BLOCKED"],
            "completion_ratio": _ratio(statuses["COMPLETED"], len(verified)),
        },
        "acceptance": {
            "linked": len(linked), "confirmed": len(confirmed),
            "completion_ratio": _ratio(len(confirmed), len(verified)),
        },
    }


def _issue(issue_type: str, component: StructuralComponent, segment: Segment, zone: StructureZone,
           detail: str, **refs) -> dict:
    return {"type": issue_type, "component_id": component.id,
            "canonical_code": component.canonical_code, "zone": zone.name,
            "segment_number": segment.number, "detail": detail, **refs}


@router.get("/projects/{project_id}/reconciliation/issues")
def reconciliation_issues(project_id: str, db: Session = Depends(get_db)):
    require_project_member(project_id)
    rows = _components(db, project_id)
    by_id = {component.id: (component, segment, zone) for component, segment, zone in rows}
    latest = _latest_events(db, project_id)
    issues: list[dict] = []

    confirmed_links: list[tuple[str, str, str | None]] = []
    if AcceptanceRecord is not None:
        for link, record in db.execute(select(ComponentAcceptanceLink, AcceptanceRecord).join(
                AcceptanceRecord, ComponentAcceptanceLink.record_id == AcceptanceRecord.id).where(
                ComponentAcceptanceLink.project_id == project_id,
                AcceptanceRecord.status == "confirmed")):
            if link.component_id in by_id:
                confirmed_links.append((link.component_id, record.id, record.confirmed_at))
    accepted = {component_id for component_id, _, _ in confirmed_links}

    for component, segment, zone in rows:
        if component.id in accepted and component.id not in latest:
            record_id = next(item[1] for item in confirmed_links if item[0] == component.id)
            issues.append(_issue("ACCEPTANCE_WITHOUT_PROGRESS", component, segment, zone,
                                 "BBNT đã xác nhận nhưng chưa có sự kiện thi công.", record_id=record_id))
        event = latest.get(component.id)
        if event is not None and event.status == "COMPLETED" and component.id not in accepted:
            issues.append(_issue("WORK_WITHOUT_ACCEPTANCE", component, segment, zone,
                                 "Thi công đã hoàn thành nhưng chưa có BBNT đã xác nhận.",
                                 event_id=event.id, event_date=event.event_date.isoformat()))
        if (component.record_origin == "SEED_IMPORT" and
                (not component.source_hash or component.source_row is None or not component.source_id)):
            issues.append(_issue("MISSING_SOURCE", component, segment, zone,
                                 "Cấu kiện nhập từ seed thiếu hash, dòng hoặc mã nguồn."))
        if component.verification != "VERIFIED":
            issues.append(_issue("UNVERIFIED_COMPONENT", component, segment, zone,
                                 "Danh mục cấu kiện chưa được duyệt.", verification=component.verification))

    for component_id, record_id, confirmed_at in confirmed_links:
        event = latest.get(component_id)
        if event is None or confirmed_at is None:
            continue
        if event.event_date > confirmed_at.date():
            component, segment, zone = by_id[component_id]
            issues.append(_issue("ACCEPTANCE_BEFORE_PROGRESS", component, segment, zone,
                                 "BBNT xác nhận trước ngày ghi nhận thi công mới nhất.",
                                 record_id=record_id, event_id=event.id,
                                 confirmed_at=confirmed_at.isoformat(),
                                 event_date=event.event_date.isoformat()))

    aliases: dict[tuple[str, str], set[str]] = defaultdict(set)
    for alias, component in db.execute(select(ComponentAlias, StructuralComponent).join(
            StructuralComponent, ComponentAlias.component_id == StructuralComponent.id).where(
            StructuralComponent.project_id == project_id)):
        aliases[(component.type, alias.alias)].add(component.id)
    for (_, code), component_ids in sorted(aliases.items()):
        if len(component_ids) < 2:
            continue
        for component_id in sorted(component_ids):
            component, segment, zone = by_id[component_id]
            issues.append(_issue("DUPLICATE_OR_AMBIGUOUS_CODE", component, segment, zone,
                                 f"Mã '{code}' dẫn tới {len(component_ids)} cấu kiện trong công trình.",
                                 related_component_ids=sorted(component_ids)))

    issues.sort(key=lambda item: (item["type"], item["canonical_code"], item["component_id"]))
    counts = Counter(item["type"] for item in issues)
    return {"project_id": project_id, "issues": issues,
            "counts": {key: counts.get(key, 0) for key in ISSUE_TYPES}}
