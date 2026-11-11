"""SQLAlchemy models for the Engineering AI module.

The canonical shared models and migration chain are owned by Codex
(``backend/app/models`` and ``backend/alembic``).  This module keeps local
fallback definitions so the module and its tests can run in isolation, exactly
like the other feature modules.  When integrating, Codex should map these
tables into the single migration chain; the table names are prefixed with
``engineering_ai_`` to avoid collisions.

No binary PDF/image content is stored here: the DB only keeps paths, hashes and
text metadata.  Files live in a private per-project storage directory and are
streamed through permission-checked API routes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

try:  # shared core when available
    from app.core.database import Base  # type: ignore
except Exception:  # pragma: no cover - fallback for isolated/test runs
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):  # type: ignore[misc]
        pass

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceDocument(Base):
    """A PDF uploaded into a single project.

    ``sha256`` is unique per project: re-uploading the same bytes returns the
    existing record instead of creating a duplicate.  ``version`` increments per
    (project, document_key) when different bytes are uploaded under the same
    original file name.  ``is_current`` marks the newest version of that family.
    """

    __tablename__ = "engineering_ai_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "sha256", name="uq_ea_document_project_sha"),
        UniqueConstraint(
            "project_id",
            "document_key",
            "version",
            name="uq_ea_document_project_key_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_effective: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drawing_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    revision: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    ocr_languages: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    warnings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_stats_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    ingest_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingest_finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class DocumentPage(Base):
    """One 1-based page of a source document, with extracted or OCR text."""

    __tablename__ = "engineering_ai_document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_ea_page_document_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_ai_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tables_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    drawing_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    revision: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    height: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warnings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class DocumentChunk(Base):
    """Character-offset chunk of a page used for retrieval and citations."""

    __tablename__ = "engineering_ai_document_chunks"
    __table_args__ = (
        UniqueConstraint("page_id", "chunk_index", name="uq_ea_chunk_page_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_ai_document_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class DocumentEmbedding(Base):
    """Optional vector metadata derived from a chunk (never an external secret)."""

    __tablename__ = "engineering_ai_document_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_ea_embedding_chunk"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class PageExtraction(Base):
    """AI page-extraction enrichment awaiting explicit engineer verification.

    This is never used as retrieval text.  The source page/chunk text remains the
    only citation source; this table stores proposed/verified structured data.
    """

    __tablename__ = "engineering_ai_page_extractions"
    __table_args__ = (
        UniqueConstraint(
            "page_id",
            "model",
            "prompt_version",
            "mode",
            name="uq_ea_page_extraction_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed", index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_json: Mapped[str] = mapped_column(Text, nullable=False)
    warnings_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verify_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class AIConversation(Base):
    """Project-scoped conversation; messages are stored as a JSON array."""

    __tablename__ = "engineering_ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    messages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class AICitation(Base):
    """Citation attached to one assistant message of a conversation."""

    __tablename__ = "engineering_ai_citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page_id: Mapped[str] = mapped_column(String(36), nullable=False)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    drawing_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    revision: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
