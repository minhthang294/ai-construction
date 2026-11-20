"""SQLAlchemy models for the Acceptance module."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

try:  # shared core when available
    from app.core.database import Base  # type: ignore
except Exception:  # pragma: no cover - isolated fallback
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):  # type: ignore[misc]
        pass

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AcceptanceRequest(Base):
    """A draft/submitted PYC (Phiếu yêu cầu nghiệm thu)."""

    __tablename__ = "acceptance_requests"
    __table_args__ = (
        UniqueConstraint("project_id", "number", name="uq_acceptance_request_project_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_item_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    daily_report_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requested_by_profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    supervisor_profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    investor_profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Validated display values used by the Excel template.  They are stored on
    # the request rather than inferred from old workbook content.
    project_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    client: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    project_location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    inspection_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    field: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # construction|electric|mechanical
    urgency: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # normal|urgent|very_urgent

    # PYC signature rows.  Never defaulted from the source workbook.
    requested_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    supervisor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    investor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Organization names printed in the BBNT participant sections.
    contractor_org: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    supervisor_org: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    investor_org: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    records: Mapped[List["AcceptanceRecord"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class AcceptanceRecord(Base):
    """A BBNT (Biên bản nghiệm thu) draft or human-confirmed record."""

    __tablename__ = "acceptance_records"
    __table_args__ = (
        UniqueConstraint("request_id", "revision", name="uq_acceptance_record_request_revision"),
        UniqueConstraint("project_id", "number", name="uq_acceptance_record_project_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("acceptance_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    request_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    request_snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    result: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # approved|conditional|rejected
    confirmer_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    record_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    start_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    design_compliance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # yes|no
    technical_compliance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # yes|no
    other_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conclusion_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    request: Mapped["AcceptanceRequest"] = relationship(back_populates="records")
    participants: Mapped[List["AcceptanceParticipant"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", order_by="AcceptanceParticipant.sort_order"
    )
    checklist: Mapped[List["AcceptanceChecklist"]] = relationship(
        back_populates="record", cascade="all, delete-orphan", order_by="AcceptanceChecklist.sort_order"
    )


class AcceptanceParticipant(Base):
    """A human participant in a BBNT record."""

    __tablename__ = "acceptance_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("acceptance_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # investor|supervisor|contractor|other
    organization: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    person_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    record: Mapped["AcceptanceRecord"] = relationship(back_populates="participants")


class AcceptanceChecklist(Base):
    """A tri-state acceptance checklist item.

    ``state`` is one of ``yes``, ``no``, ``unconfirmed``.  ``unconfirmed`` is an
    explicit state, not a missing boolean.
    """

    __tablename__ = "acceptance_checklists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("acceptance_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="unconfirmed")
    evidence_refs: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    record: Mapped["AcceptanceRecord"] = relationship(back_populates="checklist")


class AcceptanceNumberSequence(Base):
    """Per-project numbering configuration for PYC/BBNT."""

    __tablename__ = "acceptance_number_sequences"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", name="uq_acceptance_number_project_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    start_number: Mapped[int] = mapped_column(Integer, nullable=False)
    next_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    reset_policy: Mapped[str] = mapped_column(String(20), nullable=False)
    period_key: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_format: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class AcceptanceParticipantProfile(Base):
    """Project-scoped reusable participant directory entry."""

    __tablename__ = "acceptance_participant_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class ComponentAcceptanceLink(Base):
    """An explicit N-N link from a component/stage/scope to a PYC or BBNT.

    ``stage_id`` and ``scope_id`` are optional, but when present they must
    belong to ``component_id``.  A row targets exactly one of PYC or BBNT.
    The service, not the database, decides which is valid; the expression
    index also makes duplicate rows impossible when optional ids are NULL.
    """

    __tablename__ = "component_acceptance_links"
    __table_args__ = (
        CheckConstraint(
            "(request_id IS NULL) <> (record_id IS NULL)",
            name="ck_component_acceptance_link_single_target",
        ),
        Index(
            "uq_component_acceptance_link",
            "project_id",
            "component_id",
            text("coalesce(stage_id, '')"),
            text("coalesce(scope_id, '')"),
            text("coalesce(request_id, '')"),
            text("coalesce(record_id, '')"),
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    component_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("structural_components.id"), nullable=False, index=True
    )
    stage_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("component_stages.id"), nullable=True, index=True
    )
    scope_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("component_repair_scopes.id"), nullable=True, index=True
    )
    request_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("acceptance_requests.id", ondelete="CASCADE"), nullable=True, index=True
    )
    record_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("acceptance_records.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


from app.core.models import AuditLog as AcceptanceAuditLog
from app.site.models import GeneratedDocument as AcceptanceGeneratedDocument
