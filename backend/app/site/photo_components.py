"""Project-scoped component links for site photos."""

from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

try:
    from app.core.component_models import StructuralComponent
except Exception:  # pragma: no cover - isolated site runs
    StructuralComponent = None  # type: ignore[assignment]

from .models import SitePhotoComponent


def resolve_components(
    db: Session, project_id: str, component_ids: Iterable[str]
) -> tuple[list[str], str]:
    """Validate ids inside one project and return them in input order."""
    ids = list(dict.fromkeys(str(item) for item in component_ids if item))
    if not ids:
        return [], ""
    if StructuralComponent is None:
        raise ValueError("Component inventory is unavailable")
    rows = list(
        db.scalars(
            select(StructuralComponent).where(
                StructuralComponent.project_id == project_id,
                StructuralComponent.id.in_(ids),
            )
        )
    )
    found = {component.id: component for component in rows}
    missing = [component_id for component_id in ids if component_id not in found]
    if missing:
        raise ValueError("Component not found in this project")
    ordered = [found[component_id] for component_id in ids]
    label = ", ".join(component.canonical_code for component in ordered)
    return [component.id for component in ordered], label


def replace_photo_components(
    db: Session,
    photo_id: str,
    project_id: str,
    component_ids: Iterable[str],
    actor_id: Optional[str] = None,
) -> list[str]:
    ids, _ = resolve_components(db, project_id, component_ids)
    db.execute(
        delete(SitePhotoComponent).where(SitePhotoComponent.photo_id == photo_id)
    )
    for component_id in ids:
        db.add(
            SitePhotoComponent(
                photo_id=photo_id,
                component_id=component_id,
                project_id=project_id,
                created_by=actor_id,
            )
        )
    return ids


def photo_component_ids(db: Session, photo) -> list[str]:
    cached = getattr(photo, "_component_ids", None)
    if cached is not None:
        return list(cached)
    return list(
        db.scalars(
            select(SitePhotoComponent.component_id)
            .where(SitePhotoComponent.photo_id == photo.id)
            .order_by(SitePhotoComponent.component_id)
        )
    )


def photo_component_label(db: Session, photo) -> Optional[str]:
    ids = photo_component_ids(db, photo)
    if not ids:
        return None
    if StructuralComponent is None:
        return ", ".join(ids)
    codes = dict(
        db.execute(
            select(StructuralComponent.id, StructuralComponent.canonical_code).where(
                StructuralComponent.id.in_(ids)
            )
        ).all()
    )
    return ", ".join(codes.get(component_id, component_id) for component_id in ids)
