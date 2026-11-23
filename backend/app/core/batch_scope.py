"""Shared project-scoped filter for construction batches."""

from sqlalchemy import select

from .component_models import ConstructionBatch, ConstructionBatchComponent


def batch_component_ids(project_id: str, batch_id: str):
    """Selectable component ids of a batch that belongs to ``project_id``."""
    return (
        select(ConstructionBatchComponent.component_id)
        .join(ConstructionBatch, ConstructionBatch.id == ConstructionBatchComponent.batch_id)
        .where(
            ConstructionBatchComponent.batch_id == batch_id,
            ConstructionBatch.project_id == project_id,
        )
    )
