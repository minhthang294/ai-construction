from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import now, uid


class StructureZone(Base):
    __tablename__ = "structure_zones"
    __table_args__ = (UniqueConstraint("project_id", "name_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_key: Mapped[str] = mapped_column(String(255), nullable=False)


class Segment(Base):
    __tablename__ = "structure_segments"
    __table_args__ = (UniqueConstraint("zone_id", "number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    zone_id: Mapped[str] = mapped_column(ForeignKey("structure_zones.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_code: Mapped[str] = mapped_column(String(120), nullable=False)


class DesignGroup(Base):
    __tablename__ = "component_design_groups"
    __table_args__ = (UniqueConstraint("project_id", "group_type", "name", "drawing"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    group_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    drawing: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer)


class StructuralComponent(Base):
    __tablename__ = "structural_components"
    __table_args__ = (UniqueConstraint("project_id", "segment_id", "type", "canonical_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    segment_id: Mapped[str] = mapped_column(ForeignKey("structure_segments.id"), nullable=False)
    design_group_id: Mapped[str | None] = mapped_column(ForeignKey("component_design_groups.id"))
    type: Mapped[str] = mapped_column(String(12), nullable=False)
    raw_code: Mapped[str] = mapped_column(String(120), nullable=False)
    canonical_code: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(160))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    source_row: Mapped[int | None] = mapped_column(Integer)
    verification: Mapped[str] = mapped_column(String(20), nullable=False)
    record_origin: Mapped[str] = mapped_column(String(30), nullable=False, default="SEED_IMPORT")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ComponentAlias(Base):
    __tablename__ = "component_aliases"
    __table_args__ = (UniqueConstraint("project_id", "segment_id", "type", "alias"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    component_id: Mapped[str] = mapped_column(ForeignKey("structural_components.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    segment_id: Mapped[str] = mapped_column(ForeignKey("structure_segments.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(12), nullable=False)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)


class RepairScope(Base):
    __tablename__ = "component_repair_scopes"
    __table_args__ = (UniqueConstraint("component_id", "kind", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    component_id: Mapped[str] = mapped_column(ForeignKey("structural_components.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    verification: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_reference: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComponentWorkLink(Base):
    __tablename__ = "component_work_links"
    __table_args__ = (UniqueConstraint("component_id", "source_hash", "dm_row"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    component_id: Mapped[str] = mapped_column(ForeignKey("structural_components.id"), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dm_row: Mapped[int] = mapped_column(Integer, nullable=False)
    seed_sheet: Mapped[str] = mapped_column(String(40), nullable=False, default="LIEN_KET_CONG_VIEC")
    seed_row: Mapped[int] = mapped_column(Integer, nullable=False)
    work: Mapped[str] = mapped_column(Text, nullable=False)
    raw_location: Mapped[str] = mapped_column(Text, nullable=False)


class ComponentImportBatch(Base):
    __tablename__ = "component_import_batches"
    __table_args__ = (UniqueConstraint("project_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)


class StageDefinition(Base):
    __tablename__ = "component_stage_definitions"
    __table_args__ = (UniqueConstraint("project_id", "component_type", "code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    component_type: Mapped[str] = mapped_column(String(12), nullable=False)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ComponentStage(Base):
    __tablename__ = "component_stages"
    __table_args__ = (UniqueConstraint("component_id", "stage_definition_id", "repair_scope_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    component_id: Mapped[str] = mapped_column(ForeignKey("structural_components.id"), nullable=False, index=True)
    stage_definition_id: Mapped[str] = mapped_column(ForeignKey("component_stage_definitions.id"), nullable=False, index=True)
    repair_scope_id: Mapped[str] = mapped_column(ForeignKey("component_repair_scopes.id"), nullable=False, index=True)
    design_quantity: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), deferred=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class ProgressEvent(Base):
    """Append-only construction progress; shared with the site module.

    No acceptance fields: acceptance stays in its own module and is never
    inferred from a progress status.
    """

    __tablename__ = "component_progress_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    component_id: Mapped[str] = mapped_column(ForeignKey("structural_components.id"), nullable=False, index=True)
    component_stage_id: Mapped[str] = mapped_column(ForeignKey("component_stages.id"), nullable=False, index=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
