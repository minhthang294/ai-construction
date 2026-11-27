"""Read-only main-work catalogue for the site pickers."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.component_models import StageDefinition
from app.core.main_works import build_main_works

from .db import get_db
from .dependencies import require_project_member

router = APIRouter(prefix="", tags=["site-main-works"])


@router.get("/projects/{project_id}/main-works")
def list_main_works(
    project_id: str,
    type: Literal["pile", "beam"] | None = None,
    _user=Depends(require_project_member),
    db: Session = Depends(get_db),
):
    query = select(StageDefinition).where(StageDefinition.project_id == project_id)
    if type:
        query = query.where(StageDefinition.component_type == type)
    definitions = db.scalars(
        query.order_by(
            StageDefinition.component_type,
            StageDefinition.position,
            StageDefinition.code,
        )
    )
    return build_main_works(definitions)
