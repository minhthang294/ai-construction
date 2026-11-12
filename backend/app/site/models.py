"""SQLAlchemy models for the Site Report module.

The canonical shared models are owned by Codex (backend/app/models).  This module
keeps local fallback definitions so the site module and its tests can run in
isolation.  When integrated, Codex should either reuse these definitions or map
the Pydantic schemas in ``schemas.py`` to the shared ORM classes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

try:  # shared core when available
    from app.core.database import Base  # type: ignore
except Exception:  # pragma: no cover - fallback for isolated runs
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):  # type: ignore[misc]
        pass

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DailyReport(Base):
    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("project_id", "report_date", name="uq_daily_report_project_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Structured optional site notes stored as JSON text (weather, materials,
    # equipment, incidents, difficulties, safety, recommendations, other).
    site_notes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    manpower_entries: Mapped[List["ManpowerEntry"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    work_logs: Mapped[List["DailyWorkLog"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    next_day_plans: Mapped[List["NextDayPlan"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class ManpowerEntry(Base):
    __tablename__ = "manpower_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("daily_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(120), nullable=False)
    person_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    report: Mapped["DailyReport"] = relationship(back_populates="manpower_entries")


class ManpowerPreset(Base):
    """A reusable manpower row, scoped to one project and never auto-applied."""

    __tablename__ = "manpower_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(120), nullable=False)
    person_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class DailyWorkLog(Base):
    __tablename__ = "daily_work_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("daily_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_item_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    # Chosen catalog name.  The catalog can contain several rows sharing one
    # name, so the report stores the unique display name even when the row
    # itself is no longer referenced by id.
    work_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    component: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    report: Mapped["DailyReport"] = relationship(back_populates="work_logs")


class NextDayPlan(Base):
    __tablename__ = "next_day_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("daily_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    work_item_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manpower: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    equipment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dependency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    report: Mapped["DailyReport"] = relationship(back_populates="next_day_plans")


class SitePhoto(Base):
    __tablename__ = "site_photos"
    __table_args__ = (UniqueConstraint("project_id", "client_upload_id", name="uq_site_photo_client_upload"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    original_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    capture_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    gps_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    device: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    component: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    suggested_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    client_upload_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class PhotoWorkItemLink(Base):
    __tablename__ = "photo_work_item_links"
    __table_args__ = (UniqueConstraint("photo_id", "work_item_id", name="uq_photo_work_item"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    photo_id: Mapped[str] = mapped_column(String(36), ForeignKey("site_photos.id", ondelete="CASCADE"), nullable=False, index=True)
    work_item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    template_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    report_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
