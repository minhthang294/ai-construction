"""FastAPI router for the Site Report module."""

from __future__ import annotations

import mimetypes
import os
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .db import get_db
from .dependencies import (
    current_user_id,
    get_current_user,
    require_project_member,
    require_site_editor,
)
from .manpower import manpower_team_from_entries
from .models import GeneratedDocument, SitePhoto
from .photo_components import photo_component_ids
from .schemas import (
    DailyReportOut,
    DailyReportUpsertIn,
    DailyWorkLogOut,
    ExportOut,
    ExportRequestIn,
    ManpowerEntryOut,
    ManpowerPresetIn,
    ManpowerPresetOut,
    ManpowerTeamOut,
    NextDayPlanOut,
    PhotoOut,
    PhotoPatchIn,
    SiteNotesOut,
)
from .service import (
    MAX_PHOTO_BYTES,
    EmptyPhoto,
    PhotoDeleteConflict,
    PhotoDeleteFileError,
    PhotoTooLarge,
    PhotoUploadConflict,
    ProjectResourceNotFound,
    ReportNotReviewed,
    UnsupportedPhotoType,
    create_export,
    create_manpower_preset,
    create_photo,
    delete_manpower_preset,
    delete_photo,
    export_metadata,
    get_generated_document,
    get_owned_report,
    get_photo,
    get_report,
    list_exports,
    list_manpower_presets,
    list_photos,
    patch_photo,
    photo_work_item_ids,
    resolve_generated_path,
    resolve_photo_path,
    served_image_mime,
    site_notes_from_report,
    update_manpower_preset,
    upsert_report,
)

router = APIRouter(prefix="", tags=["site-report"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjectResourceNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (PhotoUploadConflict, PhotoDeleteConflict)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, PhotoDeleteFileError):
        return HTTPException(status_code=500, detail=str(exc))
    if isinstance(exc, PhotoTooLarge):
        return HTTPException(status_code=413, detail=str(exc))
    if isinstance(exc, EmptyPhoto):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, UnsupportedPhotoType):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, ReportNotReviewed):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Site report operation failed")


def _to_report_out(report, db: Session) -> DailyReportOut:
    manpower = [
        ManpowerEntryOut.model_validate(entry)
        for entry in sorted(report.manpower_entries, key=lambda item: (item.group_name.lower(), item.id))
    ]
    work_logs = [
        DailyWorkLogOut.model_validate(entry)
        for entry in sorted(report.work_logs, key=lambda item: item.id)
    ]
    plans = [
        NextDayPlanOut.model_validate(entry)
        for entry in sorted(report.next_day_plans, key=lambda item: (item.plan_date, item.id))
    ]
    return DailyReportOut(
        id=report.id,
        project_id=report.project_id,
        report_date=report.report_date,
        status=report.status,
        notes=report.notes,
        site_notes=SiteNotesOut.model_validate(site_notes_from_report(report)),
        manpower=manpower,
        manpower_team=ManpowerTeamOut.model_validate(
            manpower_team_from_entries(report.manpower_entries)
        ),
        work_logs=work_logs,
        next_day_plans=plans,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _to_photo_out(photo: SitePhoto, db: Session) -> PhotoOut:
    has_gps = photo.gps_lat is not None or photo.gps_lon is not None
    return PhotoOut(
        id=photo.id,
        project_id=photo.project_id,
        report_id=photo.report_id,
        sha256=photo.sha256,
        capture_time=photo.capture_time,
        upload_time=photo.upload_time,
        gps_lat=photo.gps_lat,
        gps_lon=photo.gps_lon,
        gps_source="exif" if has_gps else None,
        gps_confirmed=False,
        device=photo.device,
        category=photo.category,
        location=photo.location,
        component=photo.component,
        component_ids=photo_component_ids(db, photo),
        stage=photo.stage,
        suggested_caption=photo.suggested_caption,
        confirmed_caption=photo.confirmed_caption,
        mime_type=photo.mime_type,
        size_bytes=photo.size_bytes,
        filename=photo.filename,
        client_upload_id=photo.client_upload_id,
        sync_status="synced",
        work_item_ids=photo_work_item_ids(photo, db),
    )


def _to_export_out(
    doc: GeneratedDocument,
    project_id: str,
    preview_text: Optional[str] = None,
) -> ExportOut:
    metadata = export_metadata(doc)
    return ExportOut(
        id=doc.id,
        project_id=doc.project_id,
        report_id=doc.source_id,
        report_date=doc.report_date,
        format=doc.format or "",
        sha256=doc.sha256,
        snapshot_sha256=metadata.get("snapshot_sha256"),
        download_url=f"/api/v1/projects/{project_id}/generated-documents/{doc.id}/download",
        preview_text=preview_text if doc.format == "zalo" else None,
        auto_send=False,
        generated_at=doc.generated_at,
    )


def _private_file_response(
    path,
    media_type: str,
    filename: Optional[str],
    disposition: str = "inline",
):
    response = FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        content_disposition_type=disposition,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


# ---------------------------------------------------------------------------
# Daily report
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/daily-reports/{report_date}",
    response_model=DailyReportOut,
)
def get_daily_report(
    project_id: str,
    report_date: date,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    report = get_report(db, project_id, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="Daily report not found")
    return _to_report_out(report, db)


@router.put(
    "/projects/{project_id}/daily-reports/{report_date}",
    response_model=DailyReportOut,
)
def put_daily_report(
    project_id: str,
    report_date: date,
    payload: DailyReportUpsertIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    try:
        report = upsert_report(
            db,
            project_id,
            report_date,
            payload,
            actor_id=current_user_id(user),
        )
    except Exception as exc:  # mapped explicitly, never leak internals
        if isinstance(exc, (ProjectResourceNotFound,)):
            raise _http_error(exc) from exc
        raise
    return _to_report_out(report, db)


# ---------------------------------------------------------------------------
# Manpower presets
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/manpower-presets",
    response_model=List[ManpowerPresetOut],
)
def get_manpower_presets(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    return [
        ManpowerPresetOut.model_validate(preset)
        for preset in list_manpower_presets(db, project_id)
    ]


@router.post(
    "/projects/{project_id}/manpower-presets",
    response_model=ManpowerPresetOut,
    status_code=201,
)
def post_manpower_preset(
    project_id: str,
    payload: ManpowerPresetIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    try:
        preset = create_manpower_preset(
            db, project_id, payload, actor_id=current_user_id(user)
        )
    except ProjectResourceNotFound as exc:
        raise _http_error(exc) from exc
    return ManpowerPresetOut.model_validate(preset)


@router.put(
    "/projects/{project_id}/manpower-presets/{preset_id}",
    response_model=ManpowerPresetOut,
)
def put_manpower_preset(
    project_id: str,
    preset_id: str,
    payload: ManpowerPresetIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    try:
        preset = update_manpower_preset(
            db, project_id, preset_id, payload, actor_id=current_user_id(user)
        )
    except ProjectResourceNotFound as exc:
        raise _http_error(exc) from exc
    if preset is None:
        raise HTTPException(status_code=404, detail="Manpower preset not found")
    return ManpowerPresetOut.model_validate(preset)


@router.delete(
    "/projects/{project_id}/manpower-presets/{preset_id}",
    status_code=204,
)
def remove_manpower_preset(
    project_id: str,
    preset_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    if not delete_manpower_preset(
        db, project_id, preset_id, actor_id=current_user_id(user)
    ):
        raise HTTPException(status_code=404, detail="Manpower preset not found")
    return None


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/photos",
    response_model=List[PhotoOut],
    status_code=201,
)
async def upload_photos(
    project_id: str,
    files: List[UploadFile] = File(...),
    report_id: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    component: Optional[str] = Form(None),
    component_ids: Optional[str] = Form(None),
    stage: Optional[str] = Form(None),
    confirmed_caption: Optional[str] = Form(None),
    suggested_caption: Optional[str] = Form(None),
    work_item_ids: Optional[str] = Form(None),
    client_upload_ids: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    ids_list = [value.strip() for value in (work_item_ids or "").split(",") if value.strip()]
    component_id_list = [
        value.strip() for value in (component_ids or "").split(",") if value.strip()
    ]
    client_ids = [
        value.strip() for value in (client_upload_ids or "").split(",") if value.strip()
    ]
    if client_ids and len(client_ids) != len(files):
        raise HTTPException(
            status_code=422,
            detail="client_upload_ids count must match files count",
        )

    results: List[PhotoOut] = []
    for index, upload in enumerate(files):
        # Read at most the configured limit + 1 byte so a hostile upload cannot
        # exhaust memory before the size check in the service.
        data = await upload.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise _http_error(PhotoTooLarge("Photo exceeds the configured size limit"))
        try:
            photo = create_photo(
                db=db,
                project_id=project_id,
                data=data,
                filename=upload.filename,
                mime_type=upload.content_type,
                report_id=report_id,
                category=category,
                location=location,
                component=component,
                component_ids=component_id_list or None,
                stage=stage,
                confirmed_caption=confirmed_caption,
                suggested_caption=suggested_caption,
                client_upload_id=client_ids[index] if client_ids else None,
                work_item_ids=ids_list or None,
                actor_id=current_user_id(user),
            )
        except (
            EmptyPhoto,
            PhotoTooLarge,
            PhotoUploadConflict,
            ProjectResourceNotFound,
            UnsupportedPhotoType,
        ) as exc:
            raise _http_error(exc) from exc
        results.append(_to_photo_out(photo, db))
    return results


@router.get("/projects/{project_id}/photos", response_model=List[PhotoOut])
def get_photos(
    project_id: str,
    report_id: Optional[str] = None,
    category: Optional[str] = None,
    date_filter: Optional[date] = Query(None, alias="date"),
    location: Optional[str] = None,
    component: Optional[str] = None,
    component_id: Optional[str] = None,
    stage: Optional[str] = None,
    work_item_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    if report_id:
        try:
            get_owned_report(db, project_id, report_id)
        except ProjectResourceNotFound as exc:
            raise _http_error(exc) from exc
    photos = list_photos(
        db,
        project_id,
        report_id=report_id,
        category=category,
        photo_date=date_filter,
        location=location,
        component=component,
        component_id=component_id,
        stage=stage,
        work_item_id=work_item_id,
    )
    return [_to_photo_out(photo, db) for photo in photos]


@router.get("/projects/{project_id}/photos/{photo_id}/original")
def get_photo_original(
    project_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    photo = get_photo(db, project_id, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    try:
        path = resolve_photo_path(photo)
    except ProjectResourceNotFound as exc:
        raise _http_error(exc) from exc
    safe_mime = served_image_mime(photo.mime_type)
    media_type = safe_mime or "application/octet-stream"
    disposition = "inline" if safe_mime else "attachment"
    return _private_file_response(
        path,
        media_type,
        photo.filename or os.path.basename(str(path)),
        disposition=disposition,
    )


@router.patch("/projects/{project_id}/photos/{photo_id}", response_model=PhotoOut)
def patch_photo_route(
    project_id: str,
    photo_id: str,
    payload: PhotoPatchIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    try:
        photo = patch_photo(
            db,
            project_id,
            photo_id,
            payload,
            actor_id=current_user_id(user),
        )
    except (ProjectResourceNotFound, PhotoUploadConflict) as exc:
        raise _http_error(exc) from exc
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return _to_photo_out(photo, db)


@router.delete(
    "/projects/{project_id}/photos/{photo_id}",
    status_code=204,
)
def delete_photo_route(
    project_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    try:
        deleted = delete_photo(
            db,
            project_id,
            photo_id,
            actor_id=current_user_id(user),
        )
    except (ProjectResourceNotFound, PhotoDeleteConflict, PhotoDeleteFileError) as exc:
        raise _http_error(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Photo not found")
    return None


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/daily-reports/{report_date}/exports",
    response_model=ExportOut,
    status_code=201,
)
def create_export_route(
    project_id: str,
    report_date: date,
    payload: ExportRequestIn,
    db: Session = Depends(get_db),
    user=Depends(require_site_editor),
):
    report = get_report(db, project_id, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="Daily report not found")
    try:
        doc = create_export(
            db,
            project_id,
            report,
            payload.format,
            created_by=current_user_id(user),
        )
    except ReportNotReviewed as exc:
        raise _http_error(exc) from exc
    return _to_export_out(doc, project_id, getattr(doc, "_preview_text", None))


@router.get(
    "/projects/{project_id}/daily-reports/{report_date}/exports",
    response_model=List[ExportOut],
)
def list_exports_route(
    project_id: str,
    report_date: date,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    report = get_report(db, project_id, report_date)
    if report is None:
        raise HTTPException(status_code=404, detail="Daily report not found")
    docs = list_exports(db, project_id, report_id=report.id)
    return [_to_export_out(doc, project_id) for doc in docs]


@router.get("/projects/{project_id}/generated-documents/{doc_id}/download")
def download_generated(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_project_member),
):
    doc = get_generated_document(db, project_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Generated document not found")
    try:
        path = resolve_generated_path(doc)
    except ProjectResourceNotFound as exc:
        raise _http_error(exc) from exc
    media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return _private_file_response(
        path, media_type, os.path.basename(str(path)), disposition="attachment"
    )


# Progress and journal routes live in their own module but share this DB
# dependency object so dependency overrides in tests cover both routers.
from .journal import router as journal_router  # noqa: E402
from .main_works_router import router as main_works_router  # noqa: E402
from .progress import router as progress_router  # noqa: E402

router.routes.extend(progress_router.routes)
router.routes.extend(journal_router.routes)
router.routes.extend(main_works_router.routes)

# Keep the dependency imported for tests/overrides that target it explicitly.
__all__ = ["router", "get_db", "get_current_user"]
