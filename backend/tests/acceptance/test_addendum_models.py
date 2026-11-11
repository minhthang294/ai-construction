"""Model columns must match migration c7d41f2b9a10 (migration is coordinator-owned)."""
from __future__ import annotations

from app.acceptance.models import (
    AcceptanceNumberSequence,
    AcceptanceParticipantProfile,
    AcceptanceRecord,
    AcceptanceRequest,
)


def _columns(model):
    return {column.name for column in model.__table__.columns}


def test_addendum_model_columns_match_migration_contract():
    assert _columns(AcceptanceNumberSequence) == {
        "id",
        "project_id",
        "kind",
        "prefix",
        "start_number",
        "next_number",
        "width",
        "reset_policy",
        "period_key",
        "date_format",
        "created_at",
        "updated_at",
    }
    assert _columns(AcceptanceParticipantProfile) == {
        "id",
        "project_id",
        "full_name",
        "organization",
        "position",
        "role",
        "active",
        "created_at",
        "updated_at",
    }
    assert {
        "revision",
        "requested_by_profile_id",
        "supervisor_profile_id",
        "investor_profile_id",
    } <= _columns(AcceptanceRequest)
    assert {
        "number",
        "request_updated_at",
        "request_snapshot_json",
        "revision",
        "supersedes_id",
    } <= _columns(AcceptanceRecord)
    record_constraints = {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in AcceptanceRecord.__table__.constraints
        if getattr(constraint, "columns", None) is not None
    }
    assert ("request_id", "revision") in record_constraints
    assert ("number", "project_id") in record_constraints
