"""FastAPI router for the Acceptance module (PYC/BBNT)."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session

try:  # shared core
    from app.core.database import get_db as _shared_get_db  # type: ignore
except Exception:  # pragma: no cover - isolated fallback
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    _engine = create_engine("sqlite:///:memory:", future=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

    def _shared_get_db():  # type: ignore[misc]
        db = _SessionLocal()
        try:
            yield db
        finally:
            db.close()

from .dependencies import (
    current_user_id,
    require_confirmer,
    require_editor,
    require_project_member,
)
from .errors import AcceptanceError
from .models import AcceptanceGeneratedDocument
from .schemas import (
    ConfirmIn,
    DailyReportLinkOut,
    ExportIn,
    ExportOut,
    NumberingIn,
    NumberingOut,
    ParticipantProfileIn,
    ParticipantProfileOut,
    ParticipantProfileUpdate,
    PreviewOut,
    RecordIn,
    RecordOut,
    RecordUpdate,
    RequestIn,
    RequestOut,
    RequestUpdate,
    WorkItemAcceptanceHistoryOut,
)
from .service import (
    confirm_record,
    create_profile,
    create_record,
    create_record_revision,
    create_request,
    delete_profile,
    delete_request,
    download_filename,
    export_record,
    export_request,
    get_export,
    get_numbering,
    get_profile,
    get_record,
    get_request,
    get_request_daily_report,
    list_exports,
    list_profiles,
    list_records,
    list_requests,
    preview_record,
    preview_request,
    preview_request_image,
    record_payload,
    update_numbering,
    update_profile,
    update_record,
    update_request,
    storage_root,
    work_item_history,
)

router = APIRouter(prefix="", tags=["acceptance"])


def get_db():
    yield from _shared_get_db()


def _error(exc: AcceptanceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


def _export_out(project_id: str, document: AcceptanceGeneratedDocument) -> ExportOut:
    return ExportOut(
        id=document.id,
        project_id=document.project_id,
        kind=document.kind,
        source_id=document.source_id,
        format=document.format,
        sha256=document.sha256,
        template_sha256=document.template_sha256,
        download_url=f"/api/v1/projects/{project_id}/acceptance-exports/{document.id}/download",
        generated_at=document.generated_at,
    )


@router.get(
    "/projects/{project_id}/acceptance-numbering",
    response_model=list[NumberingOut],
)
def get_acceptance_numbering(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        rows = [get_numbering(db, project_id, kind) for kind in ("pyc", "bbnt")]
    except AcceptanceError as exc:
        return _error(exc)
    return [NumberingOut.model_validate(row) for row in rows]


@router.put(
    "/projects/{project_id}/acceptance-numbering/{kind}",
    response_model=NumberingOut,
)
def put_acceptance_numbering(
    project_id: str,
    kind: str,
    payload: NumberingIn,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        row = update_numbering(db, project_id, kind, payload)
    except AcceptanceError as exc:
        return _error(exc)
    return NumberingOut.model_validate(row)


@router.get(
    "/projects/{project_id}/acceptance-participants",
    response_model=list[ParticipantProfileOut],
)
def get_acceptance_participants(
    project_id: str,
    active_only: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return [ParticipantProfileOut.model_validate(item) for item in list_profiles(db, project_id, active_only=active_only)]


@router.post(
    "/projects/{project_id}/acceptance-participants",
    response_model=ParticipantProfileOut,
    status_code=status.HTTP_201_CREATED,
)
def post_acceptance_participant(
    project_id: str,
    payload: ParticipantProfileIn,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        profile = create_profile(db, project_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return ParticipantProfileOut.model_validate(profile)


@router.get(
    "/projects/{project_id}/acceptance-participants/{profile_id}",
    response_model=ParticipantProfileOut,
)
def get_acceptance_participant(
    project_id: str,
    profile_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        profile = get_profile(db, project_id, profile_id)
    except AcceptanceError as exc:
        return _error(exc)
    return ParticipantProfileOut.model_validate(profile)


@router.patch(
    "/projects/{project_id}/acceptance-participants/{profile_id}",
    response_model=ParticipantProfileOut,
)
def patch_acceptance_participant(
    project_id: str,
    profile_id: str,
    payload: ParticipantProfileUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        profile = update_profile(db, project_id, profile_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return ParticipantProfileOut.model_validate(profile)


@router.delete(
    "/projects/{project_id}/acceptance-participants/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_acceptance_participant(
    project_id: str,
    profile_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        delete_profile(db, project_id, profile_id, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return None


@router.post(
    "/projects/{project_id}/acceptance-requests",
    response_model=RequestOut,
    status_code=status.HTTP_201_CREATED,
)
def create_acceptance_request(
    project_id: str,
    payload: RequestIn,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        request = create_request(db, project_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return RequestOut.model_validate(request)


@router.get(
    "/projects/{project_id}/acceptance-requests",
    response_model=list[RequestOut],
)
def get_acceptance_requests(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return [RequestOut.model_validate(item) for item in list_requests(db, project_id)]


@router.get(
    "/projects/{project_id}/acceptance-requests/{request_id}",
    response_model=RequestOut,
)
def get_acceptance_request(
    project_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    request = get_request(db, project_id, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy PYC trong công trình")
    return RequestOut.model_validate(request)


@router.get(
    "/projects/{project_id}/acceptance-requests/{request_id}/daily-report",
    response_model=Optional[DailyReportLinkOut],
)
def get_acceptance_request_daily_report(
    project_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        report = get_request_daily_report(db, project_id, request_id)
    except AcceptanceError as exc:
        return _error(exc)
    return None if report is None else DailyReportLinkOut.model_validate(report)


@router.patch(
    "/projects/{project_id}/acceptance-requests/{request_id}",
    response_model=RequestOut,
)
def patch_acceptance_request(
    project_id: str,
    request_id: str,
    payload: RequestUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        request = update_request(db, project_id, request_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return RequestOut.model_validate(request)


@router.delete(
    "/projects/{project_id}/acceptance-requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_acceptance_request(
    project_id: str,
    request_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        delete_request(
            db,
            project_id,
            request_id,
            current_user_id(user),
            force=force,
        )
    except AcceptanceError as exc:
        return _error(exc)
    return None


@router.post(
    "/projects/{project_id}/acceptance-requests/{request_id}/exports",
    response_model=ExportOut,
    status_code=status.HTTP_201_CREATED,
)
def export_acceptance_request(
    project_id: str,
    request_id: str,
    payload: ExportIn,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        document = export_request(db, project_id, request_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return _export_out(project_id, document)


@router.get(
    "/projects/{project_id}/acceptance-requests/{request_id}/exports",
    response_model=list[ExportOut],
)
def get_acceptance_request_exports(
    project_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    request = get_request(db, project_id, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy PYC trong công trình")
    docs = list_exports(db, project_id, kind="pyc", source_id=request.id)
    return [_export_out(project_id, doc) for doc in docs]


@router.get(
    "/projects/{project_id}/acceptance-requests/{request_id}/preview",
    response_model=PreviewOut,
)
def preview_acceptance_request(
    project_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        return preview_request(db, project_id, request_id)
    except AcceptanceError as exc:
        return _error(exc)


@router.get("/projects/{project_id}/acceptance-requests/{request_id}/preview-image")
def preview_acceptance_request_image(
    project_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        image = preview_request_image(db, project_id, request_id)
    except AcceptanceError as exc:
        return _error(exc)
    response = Response(content=image, media_type="image/png")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.post(
    "/projects/{project_id}/acceptance-records",
    response_model=RecordOut,
    status_code=status.HTTP_201_CREATED,
)
def create_acceptance_record(
    project_id: str,
    payload: RecordIn,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        record = create_record(db, project_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return RecordOut.model_validate(record_payload(record, db))


@router.get(
    "/projects/{project_id}/acceptance-records",
    response_model=list[RecordOut],
)
def get_acceptance_records(
    project_id: str,
    request_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return [
        RecordOut.model_validate(record_payload(record, db))
        for record in list_records(db, project_id, request_id=request_id)
    ]


@router.get(
    "/projects/{project_id}/acceptance-records/{record_id}",
    response_model=RecordOut,
)
def get_acceptance_record(
    project_id: str,
    record_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    record = get_record(db, project_id, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy BBNT trong công trình")
    return RecordOut.model_validate(record_payload(record, db))


@router.get(
    "/projects/{project_id}/acceptance-records/{record_id}/preview",
    response_model=PreviewOut,
)
def preview_acceptance_record(
    project_id: str,
    record_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        return preview_record(db, project_id, record_id)
    except AcceptanceError as exc:
        return _error(exc)


@router.post(
    "/projects/{project_id}/acceptance-records/{record_id}/revisions",
    response_model=RecordOut,
    status_code=status.HTTP_201_CREATED,
)
def revise_acceptance_record(
    project_id: str,
    record_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        record = create_record_revision(db, project_id, record_id, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return RecordOut.model_validate(record_payload(record, db))


@router.patch(
    "/projects/{project_id}/acceptance-records/{record_id}",
    response_model=RecordOut,
)
def patch_acceptance_record(
    project_id: str,
    record_id: str,
    payload: RecordUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_editor),
):
    try:
        record = update_record(db, project_id, record_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return RecordOut.model_validate(record_payload(record, db))


@router.get(
    "/projects/{project_id}/work-items/{work_item_id}/acceptance-history",
    response_model=WorkItemAcceptanceHistoryOut,
)
def get_work_item_acceptance_history(
    project_id: str,
    work_item_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        return work_item_history(db, project_id, work_item_id)
    except AcceptanceError as exc:
        return _error(exc)


@router.post(
    "/projects/{project_id}/acceptance-records/{record_id}/confirm",
    response_model=RecordOut,
)
def confirm_acceptance_record(
    project_id: str,
    record_id: str,
    payload: ConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(require_confirmer),
):
    try:
        record = confirm_record(db, project_id, record_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return RecordOut.model_validate(record_payload(record, db))


@router.post(
    "/projects/{project_id}/acceptance-records/{record_id}/exports",
    response_model=ExportOut,
    status_code=status.HTTP_201_CREATED,
)
def export_acceptance_record(
    project_id: str,
    record_id: str,
    payload: ExportIn,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    try:
        document = export_record(db, project_id, record_id, payload, current_user_id(user))
    except AcceptanceError as exc:
        return _error(exc)
    return _export_out(project_id, document)


@router.get(
    "/projects/{project_id}/acceptance-records/{record_id}/exports",
    response_model=list[ExportOut],
)
def get_acceptance_record_exports(
    project_id: str,
    record_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    record = get_record(db, project_id, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy BBNT trong công trình")
    # A record may export its own BBNT or the linked PYC; show both in history.
    docs = list_exports(db, project_id, source_id=record.id)
    docs += list_exports(db, project_id, kind="pyc", source_id=record.request_id)
    docs = sorted({doc.id: doc for doc in docs}.values(), key=lambda d: d.generated_at, reverse=True)
    return [_export_out(project_id, doc) for doc in docs]


@router.get(
    "/projects/{project_id}/acceptance-exports",
    response_model=list[ExportOut],
)
def get_acceptance_exports(
    project_id: str,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    docs = list_exports(db, project_id, kind=kind)
    return [_export_out(project_id, doc) for doc in docs]


@router.get("/projects/{project_id}/acceptance-exports/{export_id}/download")
def download_acceptance_export(
    project_id: str,
    export_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    document = get_export(db, project_id, export_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy file export")
    path = Path(document.path)
    project_root = (storage_root() / "projects" / project_id).resolve()
    if not path.resolve().is_relative_to(project_root) or not path.is_file():
        raise HTTPException(status_code=404, detail="File export không còn trên máy chủ")
    mime = mimetypes.guess_type(path.name)[0] or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response = FileResponse(path, media_type=mime, filename=download_filename(document))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
