"""Reviewed daily journal snapshots and exports.

Snapshots freeze the exact preview the user reviewed, including confirmed photo
evidence.  Exports are rendered only from that frozen JSON, never from live
reports, progress events or acceptance records.  No acceptance result is ever
invented: only confirmed BBNT rows present at snapshot time are stored.
"""

from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .dependencies import current_user_id, require_project_member, require_site_editor
from .models import GeneratedDocument, SitePhoto
from .progress import journal_preview, render_journal_text
from .service import (
    ProjectResourceNotFound,
    _audit,
    _project_dir,
    _sanitize_filename,
    export_metadata,
    photo_evidence_ready,
    render_docx,
    render_pdf,
    resolve_generated_path,
    resolve_photo_path,
    sha256_bytes,
)

router = APIRouter(prefix="", tags=["site-journal"])


class JournalSnapshotCreateIn(BaseModel):
    reviewed: Literal[True]
    preview_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class JournalSnapshotOut(BaseModel):
    id: str
    project_id: str
    journal_date: date
    sha256: str
    reviewed_by: Optional[str] = None
    reviewed_at: datetime
    evidence_count: int
    omitted_evidence_count: int
    acceptance_count: int
    warnings: List[str] = Field(default_factory=list)
    download_url: str


class JournalExportIn(BaseModel):
    snapshot_id: str = Field(min_length=1, max_length=36)
    format: Literal["pdf", "docx", "zip"]


class JournalExportOut(BaseModel):
    id: str
    project_id: str
    snapshot_id: str
    journal_date: date
    format: str
    sha256: str
    snapshot_sha256: str
    download_url: str
    auto_send: bool = False
    generated_at: datetime


def _snapshot_dir(project_id: str, journal_date: date, snapshot_id: str) -> Path:
    return (
        _project_dir(project_id)
        / "journals"
        / journal_date.isoformat()
        / snapshot_id
    )


def _download_url(project_id: str, doc_id: str) -> str:
    return f"/api/v1/projects/{project_id}/generated-documents/{doc_id}/download"


def _snapshot_out(doc: GeneratedDocument, project_id: str) -> dict[str, Any]:
    meta = export_metadata(doc)
    return {
        "id": doc.id,
        "project_id": project_id,
        "journal_date": doc.report_date,
        "sha256": doc.sha256,
        "reviewed_by": meta.get("reviewed_by"),
        "reviewed_at": meta.get("reviewed_at") or doc.generated_at,
        "evidence_count": int(meta.get("evidence_count") or 0),
        "omitted_evidence_count": int(meta.get("omitted_evidence_count") or 0),
        "acceptance_count": int(meta.get("acceptance_count") or 0),
        "warnings": meta.get("warnings") or [],
        "download_url": _download_url(project_id, doc.id),
    }


def _export_out(doc: GeneratedDocument, project_id: str) -> dict[str, Any]:
    meta = export_metadata(doc)
    return {
        "id": doc.id,
        "project_id": project_id,
        "snapshot_id": doc.source_id or "",
        "journal_date": doc.report_date,
        "format": doc.format or "",
        "sha256": doc.sha256,
        "snapshot_sha256": meta.get("snapshot_sha256") or "",
        "download_url": _download_url(project_id, doc.id),
        "auto_send": False,
        "generated_at": doc.generated_at,
    }


def _load_snapshot(
    db: Session, project_id: str, journal_date: date, snapshot_id: str
) -> tuple[GeneratedDocument, dict[str, Any], bytes]:
    doc = db.scalar(
        select(GeneratedDocument).where(
            GeneratedDocument.id == snapshot_id,
            GeneratedDocument.project_id == project_id,
            GeneratedDocument.kind == "journal_snapshot",
            GeneratedDocument.report_date == journal_date,
        )
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Journal snapshot not found")
    try:
        path = resolve_generated_path(doc)
    except ProjectResourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    data = path.read_bytes()
    if sha256_bytes(data) != doc.sha256:
        raise HTTPException(
            status_code=409, detail="Journal snapshot file does not match its hash"
        )
    try:
        snapshot = json.loads(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Invalid journal snapshot") from exc
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("reviewed") is not True
        or snapshot.get("project_id") != project_id
        or snapshot.get("date") != journal_date.isoformat()
    ):
        raise HTTPException(status_code=409, detail="Journal snapshot was not reviewed")
    return doc, snapshot, data


def create_journal_snapshot(
    db: Session,
    project_id: str,
    journal_date: date,
    payload: JournalSnapshotCreateIn,
    actor_id: Optional[str],
) -> dict[str, Any]:
    # Rebuild from current records and require the exact reviewed preview hash.
    preview = journal_preview(db, project_id, journal_date)
    if not preview.get("snapshot_eligible"):
        raise HTTPException(
            status_code=409,
            detail="Journal preview has blockers; review the report first",
        )
    if preview.get("preview_sha256") != payload.preview_sha256:
        raise HTTPException(
            status_code=409, detail="Journal preview changed; preview again"
        )

    snapshot_id = str(uuid.uuid4())
    directory = _snapshot_dir(project_id, journal_date, snapshot_id)
    evidence_dir = directory / "evidence"
    directory.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    copied_evidence = []
    try:
        for index, item in enumerate(preview.get("evidence") or [], start=1):
            photo = db.get(SitePhoto, item["photo_id"])
            if (
                photo is None
                or photo.project_id != project_id
                or photo.sha256 != item["sha256"]
                or not photo_evidence_ready(photo)
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Evidence changed after preview; preview again",
                )
            try:
                source_path = resolve_photo_path(photo)
            except ProjectResourceNotFound as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            data = source_path.read_bytes()
            if sha256_bytes(data) != item["sha256"]:
                raise HTTPException(
                    status_code=409,
                    detail="Evidence file hash changed; preview again",
                )
            name = f"{index:02d}_{_sanitize_filename(photo.filename)}"
            (evidence_dir / name).write_bytes(data)
            copied_evidence.append(
                {**item, "relative_path": f"evidence/{name}"}
            )

        reviewed_at = datetime.now(timezone.utc)
        snapshot = {
            **preview,
            "snapshot_id": snapshot_id,
            "reviewed": True,
            "reviewed_by": actor_id,
            "reviewed_at": reviewed_at.isoformat(),
            "reviewed_preview_sha256": payload.preview_sha256,
            "evidence": copied_evidence,
        }
        # Keep the snapshot self-contained; text is regenerated at export so the
        # footer can carry the snapshot hash instead of the preview hash.
        snapshot.pop("preview_text", None)
        snapshot_bytes = json.dumps(
            snapshot, ensure_ascii=False, indent=2, sort_keys=True, default=str
        ).encode("utf-8")
        snapshot_hash = sha256_bytes(snapshot_bytes)
        snapshot_path = directory / "snapshot.json"
        snapshot_path.write_bytes(snapshot_bytes)

        doc = GeneratedDocument(
            id=snapshot_id,
            project_id=project_id,
            kind="journal_snapshot",
            source_id=None,
            path=str(snapshot_path),
            sha256=snapshot_hash,
            created_by=actor_id,
            format="json",
            report_date=journal_date,
            metadata_json=json.dumps(
                {
                    "journal_date": journal_date.isoformat(),
                    "reviewed": True,
                    "reviewed_by": actor_id,
                    "reviewed_at": reviewed_at.isoformat(),
                    "reviewed_preview_sha256": payload.preview_sha256,
                    "snapshot_sha256": snapshot_hash,
                    "evidence_count": len(copied_evidence),
                    "omitted_evidence_count": len(
                        preview.get("omitted_evidence_refs") or []
                    ),
                    "acceptance_count": int(preview.get("acceptance_count") or 0),
                    "warnings": preview.get("warnings") or [],
                    "auto_send": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        db.add(doc)
        _audit(
            db,
            project_id=project_id,
            actor_id=actor_id,
            action="create_journal_snapshot",
            entity="GeneratedDocument",
            entity_id=doc.id,
            detail=json.dumps(
                {
                    "journal_date": journal_date.isoformat(),
                    "preview_sha256": payload.preview_sha256,
                    "snapshot_sha256": snapshot_hash,
                    "evidence_count": len(copied_evidence),
                    "acceptance_count": int(preview.get("acceptance_count") or 0),
                },
                ensure_ascii=False,
            ),
        )
        db.commit()
        db.refresh(doc)
        return _snapshot_out(doc, project_id)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        db.rollback()
        raise


def _journal_export_text(snapshot: dict[str, Any], snapshot_hash: str) -> str:
    return render_journal_text(snapshot, hash_value=snapshot_hash)


def create_journal_export(
    db: Session,
    project_id: str,
    journal_date: date,
    payload: JournalExportIn,
    actor_id: Optional[str],
) -> dict[str, Any]:
    snapshot_doc, snapshot, snapshot_bytes = _load_snapshot(
        db, project_id, journal_date, payload.snapshot_id
    )
    text = _journal_export_text(snapshot, snapshot_doc.sha256)
    export_dir = (
        _project_dir(project_id)
        / "journals"
        / journal_date.isoformat()
        / "exports"
    )
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = export_dir / f"{timestamp}_{payload.format}_{uuid.uuid4().hex[:8]}"

    if payload.format == "pdf":
        out_path = base.with_suffix(".pdf")
        render_pdf(snapshot, text, out_path)
    elif payload.format == "docx":
        out_path = base.with_suffix(".docx")
        render_docx(snapshot, text, out_path)
    else:
        out_path = base.with_suffix(".zip")
        pdf_path = base.with_name(base.name + "_journal.pdf")
        docx_path = base.with_name(base.name + "_journal.docx")
        try:
            render_pdf(snapshot, text, pdf_path)
            render_docx(snapshot, text, docx_path)
            snapshot_dir = Path(snapshot_doc.path).resolve().parent
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("snapshot.json", snapshot_bytes)
                archive.writestr("journal.txt", text)
                archive.write(pdf_path, arcname="journal.pdf")
                archive.write(docx_path, arcname="journal.docx")
                for item in snapshot.get("evidence") or []:
                    relative = str(item.get("relative_path") or "")
                    candidate = (snapshot_dir / relative).resolve()
                    try:
                        candidate.relative_to(snapshot_dir)
                    except ValueError as exc:
                        raise HTTPException(
                            status_code=409,
                            detail="Snapshot evidence path is outside storage",
                        ) from exc
                    if not candidate.is_file():
                        raise HTTPException(
                            status_code=409, detail="Snapshot evidence file is missing"
                        )
                    data = candidate.read_bytes()
                    if sha256_bytes(data) != item.get("sha256"):
                        raise HTTPException(
                            status_code=409, detail="Snapshot evidence hash changed"
                        )
                    archive.writestr(f"evidence/{candidate.name}", data)
        finally:
            pdf_path.unlink(missing_ok=True)
            docx_path.unlink(missing_ok=True)

    out_bytes = out_path.read_bytes()
    meta = export_metadata(snapshot_doc)
    doc = GeneratedDocument(
        project_id=project_id,
        kind="journal_export",
        source_id=snapshot_doc.id,
        path=str(out_path),
        sha256=sha256_bytes(out_bytes),
        created_by=actor_id,
        format=payload.format,
        report_date=journal_date,
        metadata_json=json.dumps(
            {
                "journal_date": journal_date.isoformat(),
                "snapshot_sha256": snapshot_doc.sha256,
                "snapshot_id": snapshot_doc.id,
                "evidence_count": int(meta.get("evidence_count") or 0),
                "omitted_evidence_count": int(
                    meta.get("omitted_evidence_count") or 0
                ),
                "acceptance_count": int(meta.get("acceptance_count") or 0),
                "auto_send": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    db.add(doc)
    db.flush()
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="create_journal_export",
        entity="GeneratedDocument",
        entity_id=doc.id,
        detail=json.dumps(
            {
                "format": payload.format,
                "journal_date": journal_date.isoformat(),
                "snapshot_id": snapshot_doc.id,
                "snapshot_sha256": snapshot_doc.sha256,
            },
            ensure_ascii=False,
        ),
    )
    db.commit()
    db.refresh(doc)
    return _export_out(doc, project_id)


def list_journal_snapshots(
    db: Session, project_id: str, journal_date: date
) -> List[dict[str, Any]]:
    docs = db.scalars(
        select(GeneratedDocument)
        .where(
            GeneratedDocument.project_id == project_id,
            GeneratedDocument.kind == "journal_snapshot",
            GeneratedDocument.report_date == journal_date,
        )
        .order_by(GeneratedDocument.generated_at.desc(), GeneratedDocument.id)
    ).all()
    return [_snapshot_out(doc, project_id) for doc in docs]


def list_journal_exports(
    db: Session, project_id: str, journal_date: date
) -> List[dict[str, Any]]:
    docs = db.scalars(
        select(GeneratedDocument)
        .where(
            GeneratedDocument.project_id == project_id,
            GeneratedDocument.kind == "journal_export",
            GeneratedDocument.report_date == journal_date,
        )
        .order_by(GeneratedDocument.generated_at.desc(), GeneratedDocument.id)
    ).all()
    return [_export_out(doc, project_id) for doc in docs]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/journals/{journal_date}/snapshots",
    response_model=JournalSnapshotOut,
    status_code=201,
)
def post_journal_snapshot(
    project_id: str,
    journal_date: date,
    payload: JournalSnapshotCreateIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    return create_journal_snapshot(
        db, project_id, journal_date, payload, current_user_id(user)
    )


@router.get(
    "/projects/{project_id}/journals/{journal_date}/snapshots",
    response_model=List[JournalSnapshotOut],
)
def get_journal_snapshots(
    project_id: str,
    journal_date: date,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return list_journal_snapshots(db, project_id, journal_date)


@router.post(
    "/projects/{project_id}/journals/{journal_date}/exports",
    response_model=JournalExportOut,
    status_code=201,
)
def post_journal_export(
    project_id: str,
    journal_date: date,
    payload: JournalExportIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    return create_journal_export(
        db, project_id, journal_date, payload, current_user_id(user)
    )


@router.get(
    "/projects/{project_id}/journals/{journal_date}/exports",
    response_model=List[JournalExportOut],
)
def get_journal_exports(
    project_id: str,
    journal_date: date,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return list_journal_exports(db, project_id, journal_date)
