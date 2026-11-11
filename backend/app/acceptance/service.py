"""Business logic for PYC (acceptance request) and BBNT (acceptance record)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .errors import AcceptanceError, TemplateError
from .models import (
    AcceptanceAuditLog,
    AcceptanceChecklist,
    AcceptanceGeneratedDocument,
    AcceptanceNumberSequence,
    AcceptanceParticipant,
    AcceptanceParticipantProfile,
    AcceptanceRecord,
    AcceptanceRequest,
)
from .schemas import (
    ChecklistIn,
    ConfirmIn,
    ExportIn,
    NumberingIn,
    ParticipantIn,
    ParticipantProfileIn,
    ParticipantProfileUpdate,
    RecordIn,
    RecordUpdate,
    RequestIn,
    RequestUpdate,
)
from .template import copy_and_fill, sha256_file, template_path, validate_template

try:  # shared core when available
    from app.core.models import WorkItem as _SharedWorkItem  # type: ignore
except Exception:  # pragma: no cover - isolated fallback
    _SharedWorkItem = None  # type: ignore

try:  # site daily reports and photo evidence when available
    from app.site.models import DailyReport as _SiteDailyReport  # type: ignore
    from app.site.models import SitePhoto as _SitePhoto  # type: ignore
except Exception:  # pragma: no cover - isolated fallback
    _SiteDailyReport = None  # type: ignore
    _SitePhoto = None  # type: ignore

try:  # Engineering AI source documents/pages when available
    from app.engineering_ai.models import DocumentPage as _SourcePage  # type: ignore
    from app.engineering_ai.models import SourceDocument as _SourceDocument  # type: ignore
except Exception:  # pragma: no cover - isolated fallback
    _SourcePage = None  # type: ignore
    _SourceDocument = None  # type: ignore

STORAGE_ENV = "ACCEPTANCE_STORAGE"
DEFAULT_STORAGE = Path("/tmp/opencode/acceptance-storage")
LIBREOFFICE_ENV = "ACCEPTANCE_LIBREOFFICE"
PDF_TIMEOUT_ENV = "ACCEPTANCE_PDF_TIMEOUT"
DEFAULT_PDF_TIMEOUT = 120

DEFAULT_CHECKLIST_ITEMS: tuple[str, ...] = (
    "Phiếu yêu cầu nghiệm thu của nhà thầu",
    "Hồ sơ thiết kế bản vẽ thi công, chỉ dẫn kỹ thuật được chủ đầu tư phê duyệt",
    "Tiêu chuẩn, quy phạm xây dựng được áp dụng",
    "Kết quả thí nghiệm mẫu kiểm nghiệm của đối tượng nghiệm thu",
    "Nhật ký thi công",
    "Hình ảnh thi công, nghiệm thu",
    "Các tài liệu khác có liên quan",
)

FIELD_VALUES = {"construction", "electric", "mechanical"}
URGENCY_VALUES = {"normal", "urgent", "very_urgent"}
PARTICIPANT_ROLES = {"investor", "supervisor", "contractor", "other"}
TRI_STATES = {"yes", "no", "unconfirmed"}

# Hidden sampling forms contain old personnel strings.  Clear the value-bearing
# cells while keeping labels so they cannot leak old names if unhidden.
PYC_HIDDEN_SCRUB = (
    "C1", "C2", "C3",
    "B6", "F6", "B7", "B10", "D10", "E10",
    "H10", "I10", "K10",
    "D14", "D15", "D16",
    "A20", "E20", "H20",
)
BBLM_SCRUB = ("A12", "A13", "A15", "A16")

NUMBERING_KINDS = {"pyc", "bbnt"}
RESET_POLICIES = {"never", "yearly", "monthly"}
PROFILE_ROLES = {"investor", "supervisor", "contractor", "requester", "other"}
DEFAULT_NUMBERING = {
    "prefix": "PYC-",
    "start_number": 1,
    "width": 3,
    "reset_policy": "never",
    "date_format": "%Y",
}


def storage_root() -> Path:
    root = Path(os.getenv(STORAGE_ENV, str(DEFAULT_STORAGE))).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _project_export_dir(project_id: str, source_id: str) -> Path:
    path = storage_root() / "projects" / project_id / "exports" / source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _audit(
    db: Session,
    *,
    project_id: Optional[str],
    actor_id: Optional[str],
    action: str,
    entity: str,
    entity_id: str,
    detail: Optional[Mapping[str, Any]] = None,
) -> None:
    if not actor_id:
        return
    db.add(
        AcceptanceAuditLog(
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=json.dumps(detail or {}, ensure_ascii=False, default=str),
        )
    )


def get_request(db: Session, project_id: str, request_id: str) -> Optional[AcceptanceRequest]:
    return db.scalar(
        select(AcceptanceRequest).where(
            AcceptanceRequest.project_id == project_id,
            AcceptanceRequest.id == request_id,
        )
    )


def list_requests(db: Session, project_id: str) -> List[AcceptanceRequest]:
    return list(
        db.scalars(
            select(AcceptanceRequest)
            .where(AcceptanceRequest.project_id == project_id)
            .order_by(AcceptanceRequest.requested_at.desc())
        ).all()
    )


def get_request_daily_report(
    db: Session, project_id: str, request_id: str
) -> Optional[Any]:
    """Read the optional linked daily report, enforcing project ownership."""

    request = get_request(db, project_id, request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC trong công trình", "request_not_found")
    if not request.daily_report_id:
        return None
    if _SiteDailyReport is None:
        raise AcceptanceError(
            503,
            "Mô-đun báo cáo ngày không khả dụng trong môi trường này",
            "daily_report_unavailable",
        )
    report = db.get(_SiteDailyReport, request.daily_report_id)
    if report is None or report.project_id != project_id:
        raise AcceptanceError(
            404, "Báo cáo ngày không thuộc công trình này", "daily_report_not_found"
        )
    return report


def get_record(db: Session, project_id: str, record_id: str) -> Optional[AcceptanceRecord]:
    return db.scalar(
        select(AcceptanceRecord).where(
            AcceptanceRecord.project_id == project_id,
            AcceptanceRecord.id == record_id,
        )
    )


def list_records(
    db: Session, project_id: str, request_id: Optional[str] = None
) -> List[AcceptanceRecord]:
    stmt = select(AcceptanceRecord).where(AcceptanceRecord.project_id == project_id)
    if request_id:
        stmt = stmt.where(AcceptanceRecord.request_id == request_id)
    return list(db.scalars(stmt.order_by(AcceptanceRecord.created_at.desc())).all())


def _request_values(payload: RequestIn | RequestUpdate, *, include_unset: bool) -> Dict[str, Any]:
    if include_unset:
        return payload.model_dump()
    return payload.model_dump(exclude_unset=True)


def _validate_request_for_submit(values: Mapping[str, Any]) -> None:
    if not (values.get("content") or "").strip():
        raise AcceptanceError(422, "Nội dung nghiệm thu là bắt buộc khi gửi PYC", "content_required")
    if not values.get("request_date"):
        raise AcceptanceError(422, "Ngày yêu cầu nghiệm thu là bắt buộc khi gửi PYC", "request_date_required")
    if not (values.get("location") or "").strip():
        raise AcceptanceError(422, "Vị trí nghiệm thu là bắt buộc khi gửi PYC", "location_required")
    if values.get("field") not in FIELD_VALUES:
        raise AcceptanceError(422, "Lĩnh vực nghiệm thu không hợp lệ", "field_invalid")
    if values.get("urgency") not in URGENCY_VALUES:
        raise AcceptanceError(422, "Mức độ yêu cầu không hợp lệ", "urgency_invalid")


def _validate_work_item(db: Session, project_id: str, work_item_id: Optional[str]) -> None:
    """Reject a work item that does not belong to the current project.

    The shared model is imported lazily so the acceptance module still works in
    isolation.  When shared core is absent, ownership cannot be checked here.
    """

    if not work_item_id or _SharedWorkItem is None:
        return
    item = db.get(_SharedWorkItem, work_item_id)
    if item is None or item.project_id != project_id:
        raise AcceptanceError(
            404, "Công việc không thuộc công trình này", "work_item_not_found"
        )


def _validate_daily_report(
    db: Session, project_id: str, daily_report_id: Optional[str]
) -> None:
    """A linked daily report must exist in the same project."""

    if not daily_report_id or _SiteDailyReport is None:
        return
    report = db.get(_SiteDailyReport, daily_report_id)
    if report is None or report.project_id != project_id:
        raise AcceptanceError(
            404, "Báo cáo ngày không thuộc công trình này", "daily_report_not_found"
        )


def _photo_is_confirmed(photo: Any) -> bool:
    # Mirrors the site module policy: a user-confirmed caption or a
    # user-selected category is required before a photo can be evidence.
    return bool(
        (getattr(photo, "confirmed_caption", None) or "").strip()
        or (getattr(photo, "category", None) or "").strip()
    )


def _validate_evidence_photo(db: Session, project_id: str, photo_id: str) -> None:
    if _SitePhoto is None:
        return
    photo = db.get(_SitePhoto, photo_id)
    if photo is None or photo.project_id != project_id:
        raise AcceptanceError(
            404,
            "Ảnh bằng chứng không tồn tại hoặc không thuộc công trình này",
            "evidence_photo_not_found",
        )
    if not _photo_is_confirmed(photo):
        raise AcceptanceError(
            422,
            "Ảnh bằng chứng chưa được xác nhận chú thích hoặc phân loại",
            "evidence_photo_unconfirmed",
        )


def _validate_evidence_document(db: Session, project_id: str, document_id: str) -> None:
    if _SourceDocument is None:
        return
    document = db.get(_SourceDocument, document_id)
    if document is None or document.project_id != project_id:
        raise AcceptanceError(
            404,
            "Tài liệu nguồn không tồn tại hoặc không thuộc công trình này",
            "evidence_document_not_found",
        )


def _validate_evidence_page_id(db: Session, project_id: str, page_id: str) -> None:
    if _SourcePage is None:
        return
    page = db.get(_SourcePage, page_id)
    if page is None or page.project_id != project_id:
        raise AcceptanceError(
            404,
            "Trang tài liệu không tồn tại hoặc không thuộc công trình này",
            "evidence_page_not_found",
        )


def _validate_evidence_page_number(
    db: Session, project_id: str, document_id: str, page_number: int
) -> None:
    _validate_evidence_document(db, project_id, document_id)
    if _SourcePage is None:
        return
    page = db.scalar(
        select(_SourcePage).where(
            _SourcePage.document_id == document_id,
            _SourcePage.page_number == page_number,
        )
    )
    if page is None or page.project_id != project_id:
        raise AcceptanceError(
            404,
            "Trang tài liệu không tồn tại hoặc không thuộc công trình này",
            "evidence_page_not_found",
        )


def _validate_evidence_refs(db: Session, project_id: str, refs: Sequence[str]) -> None:
    """Validate every checklist evidence reference.

    Supported string forms:
    - ``<photo_id>`` or ``photo:<photo_id>``: site photo in this project with a
      human-confirmed caption/category.
    - ``document:<document_id>``: Engineering AI source document in this project.
    - ``page:<page_id>``: Engineering AI document page in this project.
    - ``page:<document_id>:<page_number>`` or
      ``page:<document_id>#<page_number>``: resolved page in this project.

    Arbitrary unresolved IDs are rejected instead of being stored as opaque
    evidence.
    """

    for raw_ref in refs:
        ref = (raw_ref or "").strip()
        if not ref:
            raise AcceptanceError(422, "Bằng chứng rỗng không hợp lệ", "evidence_ref_invalid")

        lowered = ref.lower()
        if lowered.startswith("photo:"):
            photo_id = ref[len("photo:") :].strip()
            if not photo_id:
                raise AcceptanceError(422, "Thiếu mã ảnh bằng chứng", "evidence_ref_invalid")
            _validate_evidence_photo(db, project_id, photo_id)
            continue

        if lowered.startswith("document:"):
            document_id = ref[len("document:") :].strip()
            if not document_id:
                raise AcceptanceError(422, "Thiếu mã tài liệu nguồn", "evidence_ref_invalid")
            _validate_evidence_document(db, project_id, document_id)
            continue

        if lowered.startswith("page:"):
            target = ref[len("page:") :].strip()
            if not target:
                raise AcceptanceError(422, "Thiếu mã trang tài liệu", "evidence_ref_invalid")
            if "#" in target:
                document_id, page_text = target.rsplit("#", 1)
            elif ":" in target:
                document_id, page_text = target.rsplit(":", 1)
            else:
                # A bare page id.
                _validate_evidence_page_id(db, project_id, target)
                continue
            document_id = document_id.strip()
            try:
                page_number = int(page_text.strip())
            except ValueError as exc:
                raise AcceptanceError(
                    422, "Số trang bằng chứng không hợp lệ", "evidence_ref_invalid"
                ) from exc
            if not document_id or page_number < 1:
                raise AcceptanceError(
                    422, "Số trang bằng chứng không hợp lệ", "evidence_ref_invalid"
                )
            _validate_evidence_page_number(db, project_id, document_id, page_number)
            continue

        if re.match(r"^[a-z][a-z0-9_]*:", lowered):
            raise AcceptanceError(
                422,
                f"Loại bằng chứng không được hỗ trợ: {ref.split(':', 1)[0]}",
                "evidence_ref_invalid",
            )

        # Legacy behavior: a bare ref is a site photo id.
        _validate_evidence_photo(db, project_id, ref)


def _period_key(reset_policy: str) -> str:
    now = datetime.now(timezone.utc)
    if reset_policy == "yearly":
        return now.strftime("%Y")
    if reset_policy == "monthly":
        return now.strftime("%Y-%m")
    return "never"


def _sequence_defaults(project_id: str, kind: str) -> Dict[str, Any]:
    prefix = "PYC-" if kind == "pyc" else "BBNT-"
    return {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "kind": kind,
        "prefix": prefix,
        "start_number": DEFAULT_NUMBERING["start_number"],
        "next_number": DEFAULT_NUMBERING["start_number"],
        "width": DEFAULT_NUMBERING["width"],
        "reset_policy": DEFAULT_NUMBERING["reset_policy"],
        "period_key": "never",
        "date_format": DEFAULT_NUMBERING["date_format"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def _ensure_number_sequence(db: Session, project_id: str, kind: str) -> AcceptanceNumberSequence:
    row = db.scalar(
        select(AcceptanceNumberSequence).where(
            AcceptanceNumberSequence.project_id == project_id,
            AcceptanceNumberSequence.kind == kind,
        )
    )
    if row is not None:
        return row
    values = _sequence_defaults(project_id, kind)
    if db.bind is not None and db.bind.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        db.execute(
            sqlite_insert(AcceptanceNumberSequence)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["project_id", "kind"])
        )
    else:  # pragma: no cover - production currently SQLite
        db.add(AcceptanceNumberSequence(**values))
    db.flush()
    row = db.scalar(
        select(AcceptanceNumberSequence).where(
            AcceptanceNumberSequence.project_id == project_id,
            AcceptanceNumberSequence.kind == kind,
        )
    )
    if row is None:
        raise AcceptanceError(500, "Không khởi tạo được dãy số nghiệm thu", "numbering_unavailable")
    return row


def _sequence_configured(db: Session, project_id: str, kind: str) -> bool:
    return (
        db.scalar(
            select(AcceptanceNumberSequence.id).where(
                AcceptanceNumberSequence.project_id == project_id,
                AcceptanceNumberSequence.kind == kind,
            )
        )
        is not None
    )


def _format_sequence_number(config: AcceptanceNumberSequence, sequence: int) -> str:
    period = ""
    if config.reset_policy != "never" and config.date_format:
        period = datetime.now(timezone.utc).strftime(config.date_format)
    width = max(1, int(config.width or 1))
    return f"{config.prefix}{period}{sequence:0{width}d}"


def _allocate_number(db: Session, project_id: str, kind: str) -> str:
    """Allocate one number using an atomic UPDATE ... RETURNING."""

    if kind not in NUMBERING_KINDS:
        raise AcceptanceError(422, "Loại số nghiệm thu không hợp lệ", "numbering_kind_invalid")
    config = _ensure_number_sequence(db, project_id, kind)
    period = _period_key(config.reset_policy)
    now = datetime.now(timezone.utc)

    allocated: Optional[int] = db.execute(
        update(AcceptanceNumberSequence)
        .where(
            AcceptanceNumberSequence.project_id == project_id,
            AcceptanceNumberSequence.kind == kind,
            AcceptanceNumberSequence.period_key == period,
        )
        .values(
            next_number=AcceptanceNumberSequence.next_number + 1,
            updated_at=now,
        )
        .returning(AcceptanceNumberSequence.next_number - 1)
    ).scalar_one_or_none()

    if allocated is None:
        allocated = db.execute(
            update(AcceptanceNumberSequence)
            .where(
                AcceptanceNumberSequence.project_id == project_id,
                AcceptanceNumberSequence.kind == kind,
                AcceptanceNumberSequence.period_key != period,
            )
            .values(
                next_number=AcceptanceNumberSequence.start_number + 1,
                period_key=period,
                updated_at=now,
            )
            .returning(AcceptanceNumberSequence.start_number)
        ).scalar_one_or_none()

    if allocated is None:
        # Another writer won the reset race; retry the increment once.
        allocated = db.execute(
            update(AcceptanceNumberSequence)
            .where(
                AcceptanceNumberSequence.project_id == project_id,
                AcceptanceNumberSequence.kind == kind,
                AcceptanceNumberSequence.period_key == period,
            )
            .values(
                next_number=AcceptanceNumberSequence.next_number + 1,
                updated_at=now,
            )
            .returning(AcceptanceNumberSequence.next_number - 1)
        ).scalar_one_or_none()

    if allocated is None:
        raise AcceptanceError(500, "Không cấp được số nghiệm thu", "numbering_failed")
    db.flush()
    db.refresh(config)
    return _format_sequence_number(config, int(allocated))


def get_numbering(db: Session, project_id: str, kind: str) -> AcceptanceNumberSequence:
    if kind not in NUMBERING_KINDS:
        raise AcceptanceError(422, "Loại số nghiệm thu không hợp lệ", "numbering_kind_invalid")
    row = db.scalar(
        select(AcceptanceNumberSequence).where(
            AcceptanceNumberSequence.project_id == project_id,
            AcceptanceNumberSequence.kind == kind,
        )
    )
    if row is not None:
        return row
    values = _sequence_defaults(project_id, kind)
    return AcceptanceNumberSequence(**values)


def update_numbering(
    db: Session, project_id: str, kind: str, payload: NumberingIn
) -> AcceptanceNumberSequence:
    if kind not in NUMBERING_KINDS:
        raise AcceptanceError(422, "Loại số nghiệm thu không hợp lệ", "numbering_kind_invalid")
    if payload.reset_policy not in RESET_POLICIES:
        raise AcceptanceError(422, "Chính sách đánh lại số không hợp lệ", "numbering_policy_invalid")
    config = db.scalar(
        select(AcceptanceNumberSequence).where(
            AcceptanceNumberSequence.project_id == project_id,
            AcceptanceNumberSequence.kind == kind,
        )
    )
    period = _period_key(payload.reset_policy)
    if config is None:
        config = AcceptanceNumberSequence(
            project_id=project_id,
            kind=kind,
            prefix=payload.prefix,
            start_number=payload.start_number,
            next_number=payload.start_number,
            width=payload.width,
            reset_policy=payload.reset_policy,
            period_key=period,
            date_format=payload.date_format,
        )
        db.add(config)
    else:
        config.prefix = payload.prefix
        config.start_number = payload.start_number
        config.next_number = payload.start_number
        config.width = payload.width
        config.reset_policy = payload.reset_policy
        config.period_key = period
        config.date_format = payload.date_format
    db.commit()
    db.refresh(config)
    return config


def _get_profile(
    db: Session, project_id: str, profile_id: str, *, require_active: bool = True
) -> AcceptanceParticipantProfile:
    profile = db.get(AcceptanceParticipantProfile, profile_id)
    if profile is None or profile.project_id != project_id:
        raise AcceptanceError(
            404, "Người tham gia không thuộc công trình này", "participant_profile_not_found"
        )
    if require_active and not profile.active:
        raise AcceptanceError(422, "Người tham gia đã ngừng hoạt động", "participant_profile_inactive")
    return profile


def get_profile(
    db: Session, project_id: str, profile_id: str
) -> AcceptanceParticipantProfile:
    return _get_profile(db, project_id, profile_id, require_active=False)


def list_profiles(
    db: Session, project_id: str, *, active_only: bool = False
) -> List[AcceptanceParticipantProfile]:
    stmt = select(AcceptanceParticipantProfile).where(
        AcceptanceParticipantProfile.project_id == project_id
    )
    if active_only:
        stmt = stmt.where(AcceptanceParticipantProfile.active.is_(True))
    return list(
        db.scalars(
            stmt.order_by(
                AcceptanceParticipantProfile.active.desc(),
                AcceptanceParticipantProfile.full_name.asc(),
            )
        ).all()
    )


def create_profile(
    db: Session, project_id: str, payload: ParticipantProfileIn, actor_id: Optional[str]
) -> AcceptanceParticipantProfile:
    if payload.role not in PROFILE_ROLES:
        raise AcceptanceError(422, "Vai trò người tham gia không hợp lệ", "participant_role_invalid")
    profile = AcceptanceParticipantProfile(
        project_id=project_id,
        full_name=payload.full_name,
        organization=payload.organization,
        position=payload.position,
        role=payload.role,
        active=payload.active,
    )
    db.add(profile)
    db.flush()
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="create",
        entity="AcceptanceParticipantProfile",
        entity_id=profile.id,
        detail={"role": profile.role, "active": profile.active},
    )
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(
    db: Session,
    project_id: str,
    profile_id: str,
    payload: ParticipantProfileUpdate,
    actor_id: Optional[str],
) -> AcceptanceParticipantProfile:
    profile = _get_profile(db, project_id, profile_id, require_active=False)
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in PROFILE_ROLES:
        raise AcceptanceError(422, "Vai trò người tham gia không hợp lệ", "participant_role_invalid")
    if "full_name" in data and not (data["full_name"] or "").strip():
        raise AcceptanceError(422, "Họ tên không được để trống", "participant_name_required")
    for key, value in data.items():
        setattr(profile, key, value)
    profile.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="update",
        entity="AcceptanceParticipantProfile",
        entity_id=profile.id,
        detail={"fields": sorted(data.keys())},
    )
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, project_id: str, profile_id: str, actor_id: Optional[str]) -> None:
    profile = _get_profile(db, project_id, profile_id, require_active=False)
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="delete",
        entity="AcceptanceParticipantProfile",
        entity_id=profile.id,
        detail={"full_name": profile.full_name},
    )
    db.delete(profile)
    db.commit()


def _apply_request_profiles(
    db: Session, project_id: str, values: Dict[str, Any]
) -> None:
    mappings = (
        ("requested_by_profile_id", "requested_by_name", "contractor_org"),
        ("supervisor_profile_id", "supervisor_name", "supervisor_org"),
        ("investor_profile_id", "investor_name", "investor_org"),
    )
    for id_key, name_key, org_key in mappings:
        profile_id = values.get(id_key)
        if not profile_id:
            continue
        profile = _get_profile(db, project_id, profile_id)
        values[name_key] = profile.full_name
        if profile.organization:
            values[org_key] = profile.organization


def _prefill_participants(
    db: Session, request: AcceptanceRequest
) -> List[ParticipantIn]:
    result: List[ParticipantIn] = []
    mapping = (
        (request.investor_profile_id, "investor"),
        (request.supervisor_profile_id, "supervisor"),
        (request.requested_by_profile_id, "contractor"),
    )
    for profile_id, role in mapping:
        if not profile_id:
            continue
        profile = db.get(AcceptanceParticipantProfile, profile_id)
        if profile is None or profile.project_id != request.project_id or not profile.active:
            continue
        result.append(
            ParticipantIn(
                role=role,
                person_name=profile.full_name,
                organization=profile.organization,
                position=profile.position,
                sort_order=len(result),
            )
        )

    # Reuse names already entered on the PYC when no profile was selected.  The
    # values are copied verbatim, never invented, and the BBNT UI still asks the
    # user to review them before confirmation.
    present_roles = {item.role for item in result}
    fallbacks = (
        ("investor", request.investor_name, request.investor_org),
        ("supervisor", request.supervisor_name, request.supervisor_org),
        ("contractor", request.requested_by_name, request.contractor_org),
    )
    for role, name, organization in fallbacks:
        if role in present_roles:
            continue
        clean_name = (name or "").strip()
        if not clean_name:
            continue
        result.append(
            ParticipantIn(
                role=role,
                person_name=clean_name,
                organization=(organization or "").strip() or None,
                position=None,
                sort_order=len(result),
            )
        )
    return result


SNAPSHOT_FIELDS = (
    "project_name",
    "client",
    "project_location",
    "location",
    "request_date",
    "inspection_time",
    "content",
    "subject",
    "field",
    "urgency",
    "requested_by_name",
    "supervisor_name",
    "investor_name",
    "contractor_org",
    "supervisor_org",
    "investor_org",
    "work_item_id",
    "daily_report_id",
    "number",
    "revision",
)


def _request_snapshot_json(request: AcceptanceRequest) -> str:
    data: Dict[str, Any] = {}
    for field in SNAPSHOT_FIELDS:
        value = getattr(request, field, None)
        data[field] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return json.dumps(data, ensure_ascii=False)


def _record_request_view(
    record: AcceptanceRecord, current: Optional[AcceptanceRequest]
) -> Optional[Any]:
    """Return the frozen PYC view for an issued record, or the live PYC.

    Records created before the snapshot column existed fall back to the live
    request so old data remains exportable.
    """

    if not record.request_snapshot_json:
        return current
    try:
        data = json.loads(record.request_snapshot_json)
    except (TypeError, ValueError):
        return current
    if not isinstance(data, dict):
        return current
    request_date = data.get("request_date")
    if isinstance(request_date, str) and request_date:
        try:
            data["request_date"] = date.fromisoformat(request_date)
        except ValueError:
            pass
    return SimpleNamespace(**data)


def create_request(
    db: Session, project_id: str, payload: RequestIn, actor_id: Optional[str]
) -> AcceptanceRequest:
    values = payload.model_dump()
    requested_number = (values.pop("number", None) or "").strip()
    _validate_work_item(db, project_id, values.get("work_item_id"))
    _validate_daily_report(db, project_id, values.get("daily_report_id"))
    if payload.status == "submitted":
        _validate_request_for_submit(values)

    _apply_request_profiles(db, project_id, values)
    from app.core.models import Project

    project = db.get(Project, project_id)
    if project is not None:
        values["project_name"] = values["project_name"] or project.name
        values["client"] = values["client"] or project.client
        values["project_location"] = values["project_location"] or project.location

    attempts = 0
    while True:
        attempts += 1
        number = requested_number or _allocate_number(db, project_id, "pyc")
        duplicate = db.scalar(
            select(AcceptanceRequest.id).where(
                AcceptanceRequest.project_id == project_id,
                AcceptanceRequest.number == number,
            )
        )
        if duplicate is None:
            break
        if requested_number:
            raise AcceptanceError(409, "Số PYC đã tồn tại trong công trình", "request_number_conflict")
        if attempts >= 5:
            raise AcceptanceError(409, "Không cấp được số PYC duy nhất", "request_number_conflict")

    values["number"] = number
    request = AcceptanceRequest(project_id=project_id, **values)
    db.add(request)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AcceptanceError(409, "Số PYC đã tồn tại trong công trình", "request_number_conflict") from exc
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="create",
        entity="AcceptanceRequest",
        entity_id=request.id,
        detail={"number": request.number, "status": request.status},
    )
    db.commit()
    db.refresh(request)
    return request


def update_request(
    db: Session, project_id: str, request_id: str, payload: RequestUpdate, actor_id: Optional[str]
) -> AcceptanceRequest:
    request = get_request(db, project_id, request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC trong công trình", "request_not_found")

    data = _request_values(payload, include_unset=False)
    if "number" in data and data["number"] != request.number:
        duplicate = db.scalar(
            select(AcceptanceRequest).where(
                AcceptanceRequest.project_id == project_id,
                AcceptanceRequest.number == data["number"],
                AcceptanceRequest.id != request.id,
            )
        )
        if duplicate is not None:
            raise AcceptanceError(409, "Số PYC đã tồn tại trong công trình", "request_number_conflict")

    if "work_item_id" in data:
        _validate_work_item(db, project_id, data.get("work_item_id"))
    if "daily_report_id" in data:
        _validate_daily_report(db, project_id, data.get("daily_report_id"))
    _apply_request_profiles(db, project_id, data)

    merged = {
        column.name: getattr(request, column.name)
        for column in AcceptanceRequest.__table__.columns
    }
    merged.update(data)
    if data.get("status") == "submitted":
        _validate_request_for_submit(merged)

    for key, value in data.items():
        setattr(request, key, value)
    request.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="update",
        entity="AcceptanceRequest",
        entity_id=request.id,
        detail={"fields": sorted(data.keys()), "status": request.status},
    )
    db.commit()
    db.refresh(request)
    return request


def _replace_participants(db: Session, record: AcceptanceRecord, items: Sequence[ParticipantIn]) -> None:
    role_counts: Dict[str, int] = {}
    for item in items:
        slot_role = "contractor" if item.role == "requester" else item.role
        role_counts[slot_role] = role_counts.get(slot_role, 0) + 1
        if role_counts[slot_role] > 2:
            raise AcceptanceError(
                422, "Mỗi vai trò chỉ có tối đa 2 người trong mẫu BBNT", "participant_slot_overflow"
            )
    for existing in list(record.participants):
        db.delete(existing)
    db.flush()
    for index, item in enumerate(items):
        db.add(
            AcceptanceParticipant(
                project_id=record.project_id,
                record_id=record.id,
                role=item.role,
                person_name=item.person_name,
                organization=item.organization,
                position=item.position,
                sort_order=item.sort_order if item.sort_order else index,
            )
        )


def _replace_checklist(db: Session, record: AcceptanceRecord, items: Sequence[ChecklistIn]) -> None:
    for existing in list(record.checklist):
        db.delete(existing)
    db.flush()
    for index, item in enumerate(items):
        if item.state not in TRI_STATES:
            raise AcceptanceError(422, "Trạng thái checklist không hợp lệ", "checklist_state_invalid")
        _validate_evidence_refs(db, record.project_id, item.evidence_refs)
        db.add(
            AcceptanceChecklist(
                project_id=record.project_id,
                record_id=record.id,
                item=item.item,
                state=item.state,
                evidence_refs=json.dumps(item.evidence_refs, ensure_ascii=False),
                note=item.note,
                sort_order=item.sort_order if item.sort_order else index,
            )
        )


def _seed_unconfirmed_checklist(db: Session, record: AcceptanceRecord) -> None:
    for index, item in enumerate(DEFAULT_CHECKLIST_ITEMS):
        db.add(
            AcceptanceChecklist(
                project_id=record.project_id,
                record_id=record.id,
                item=item,
                state="unconfirmed",
                evidence_refs="[]",
                sort_order=index,
            )
        )


def _record_number(
    db: Session,
    project_id: str,
    request: AcceptanceRequest,
    requested_number: Optional[str],
    *,
    revision: int = 1,
) -> str:
    explicit = (requested_number or "").strip()
    if explicit:
        return explicit
    if _sequence_configured(db, project_id, "bbnt"):
        return _allocate_number(db, project_id, "bbnt")
    if revision > 1:
        return f"{request.number}-R{revision}"
    return request.number


def create_record(
    db: Session, project_id: str, payload: RecordIn, actor_id: Optional[str]
) -> AcceptanceRecord:
    request = get_request(db, project_id, payload.request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC trong công trình", "request_not_found")
    duplicate = db.scalar(
        select(AcceptanceRecord.id).where(
            AcceptanceRecord.request_id == request.id,
            AcceptanceRecord.revision == 1,
        )
    )
    if duplicate is not None:
        raise AcceptanceError(409, "PYC đã có BBNT; hãy tạo revision mới", "record_exists")

    number = _record_number(db, project_id, request, payload.number)
    if db.scalar(
        select(AcceptanceRecord.id).where(
            AcceptanceRecord.project_id == project_id,
            AcceptanceRecord.number == number,
        )
    ):
        raise AcceptanceError(409, "Số BBNT đã tồn tại trong công trình", "record_number_conflict")

    participants = (
        payload.participants
        if payload.participants is not None
        else _prefill_participants(db, request)
    )
    record = AcceptanceRecord(
        project_id=project_id,
        request_id=request.id,
        number=number,
        request_updated_at=request.updated_at,
        request_snapshot_json=_request_snapshot_json(request),
        revision=1,
        record_date=payload.record_date or request.request_date,
        start_time=payload.start_time or request.inspection_time,
        end_time=payload.end_time,
        design_compliance=payload.design_compliance,
        technical_compliance=payload.technical_compliance,
        other_notes=payload.other_notes,
        conclusion_note=payload.conclusion_note,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AcceptanceError(409, "Số BBNT đã tồn tại trong công trình", "record_number_conflict") from exc

    _replace_participants(db, record, participants or [])
    if payload.checklist:
        _replace_checklist(db, record, payload.checklist)
    else:
        _seed_unconfirmed_checklist(db, record)

    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="create",
        entity="AcceptanceRecord",
        entity_id=record.id,
        detail={
            "request_id": request.id,
            "number": record.number,
            "revision": record.revision,
            "status": record.status,
        },
    )
    db.commit()
    db.refresh(record)
    return record


def create_record_revision(
    db: Session, project_id: str, record_id: str, actor_id: Optional[str]
) -> AcceptanceRecord:
    previous = get_record(db, project_id, record_id)
    if previous is None:
        raise AcceptanceError(404, "Không tìm thấy BBNT trong công trình", "record_not_found")
    request = db.get(AcceptanceRequest, previous.request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC của BBNT", "request_not_found")
    next_revision = (
        db.scalar(
            select(AcceptanceRecord.revision)
            .where(AcceptanceRecord.request_id == previous.request_id)
            .order_by(AcceptanceRecord.revision.desc())
            .limit(1)
        )
        or previous.revision
    ) + 1
    number = _record_number(db, project_id, request, None, revision=next_revision)
    if db.scalar(
        select(AcceptanceRecord.id).where(
            AcceptanceRecord.project_id == project_id,
            AcceptanceRecord.number == number,
        )
    ):
        raise AcceptanceError(409, "Số BBNT đã tồn tại trong công trình", "record_number_conflict")

    record = AcceptanceRecord(
        project_id=project_id,
        request_id=previous.request_id,
        number=number,
        request_updated_at=request.updated_at,
        request_snapshot_json=_request_snapshot_json(request),
        revision=next_revision,
        supersedes_id=previous.id,
        status="draft",
        result=None,
        confirmer_id=None,
        confirmed_at=None,
        record_date=previous.record_date,
        start_time=previous.start_time,
        end_time=previous.end_time,
        design_compliance=previous.design_compliance,
        technical_compliance=previous.technical_compliance,
        other_notes=previous.other_notes,
        conclusion_note=previous.conclusion_note,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AcceptanceError(409, "Số BBNT đã tồn tại trong công trình", "record_number_conflict") from exc

    _replace_participants(
        db,
        record,
        [
            ParticipantIn(
                role=item.role,
                person_name=item.person_name,
                organization=item.organization,
                position=item.position,
                sort_order=item.sort_order,
            )
            for item in previous.participants
        ],
    )
    _replace_checklist(
        db,
        record,
        [
            ChecklistIn(
                item=item.item,
                state="unconfirmed",
                evidence_refs=_parse_evidence(item.evidence_refs),
                note=item.note,
                sort_order=item.sort_order,
            )
            for item in previous.checklist
        ],
    )
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="revision",
        entity="AcceptanceRecord",
        entity_id=record.id,
        detail={"supersedes_id": previous.id, "revision": record.revision},
    )
    db.commit()
    db.refresh(record)
    return record


def update_record(
    db: Session, project_id: str, record_id: str, payload: RecordUpdate, actor_id: Optional[str]
) -> AcceptanceRecord:
    record = get_record(db, project_id, record_id)
    if record is None:
        raise AcceptanceError(404, "Không tìm thấy BBNT trong công trình", "record_not_found")
    if record.status == "confirmed":
        raise AcceptanceError(409, "BBNT đã được xác nhận, không thể sửa", "record_confirmed")

    data = payload.model_dump(exclude_unset=True)
    for key in (
        "record_date",
        "start_time",
        "end_time",
        "design_compliance",
        "technical_compliance",
        "other_notes",
        "conclusion_note",
    ):
        if key in data:
            setattr(record, key, data[key])

    if "participants" in data:
        _replace_participants(db, record, payload.participants or [])
    if "checklist" in data:
        _replace_checklist(db, record, payload.checklist or [])

    record.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="update",
        entity="AcceptanceRecord",
        entity_id=record.id,
        detail={"fields": sorted(data.keys())},
    )
    db.commit()
    db.refresh(record)
    return record


def _parse_evidence(raw: str) -> List[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def checklist_payload(record: AcceptanceRecord) -> List[Dict[str, Any]]:
    return [
        {
            "id": item.id,
            "item": item.item,
            "state": item.state,
            "evidence_refs": _parse_evidence(item.evidence_refs),
            "note": item.note,
            "sort_order": item.sort_order,
        }
        for item in record.checklist
    ]


def participants_payload(record: AcceptanceRecord) -> List[Dict[str, Any]]:
    return [
        {
            "id": item.id,
            "role": item.role,
            "person_name": item.person_name,
            "organization": item.organization,
            "position": item.position,
            "sort_order": item.sort_order,
        }
        for item in record.participants
    ]


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reuse_payload(
    db: Optional[Session], record: AcceptanceRecord, request: Optional[AcceptanceRequest]
) -> Dict[str, Any]:
    view = _record_request_view(record, request)
    if view is None:
        return {}
    reused: Dict[str, Any] = {
        "work_item_id": view.work_item_id,
        "work_item_name": None,
        "location": view.location,
        "daily_report_id": view.daily_report_id,
        "request_date": view.request_date.isoformat() if view.request_date else None,
        "inspection_time": view.inspection_time,
        "confirmed_photos": [],
        "technical_documents": [],
    }
    if db is not None:
        if view.work_item_id and _SharedWorkItem is not None:
            item = db.get(_SharedWorkItem, view.work_item_id)
            if item is not None and item.project_id == record.project_id:
                reused["work_item_name"] = item.name
        if view.daily_report_id and _SitePhoto is not None:
            photos = db.scalars(
                select(_SitePhoto).where(
                    _SitePhoto.project_id == record.project_id,
                    _SitePhoto.report_id == view.daily_report_id,
                )
            ).all()
            reused["confirmed_photos"] = [
                photo.id for photo in photos if _photo_is_confirmed(photo)
            ]
        if _SourceDocument is not None:
            documents = db.scalars(
                select(_SourceDocument)
                .where(
                    _SourceDocument.project_id == record.project_id,
                    _SourceDocument.status == "ready",
                )
                .order_by(_SourceDocument.created_at.desc())
                .limit(50)
            ).all()
            reused["technical_documents"] = [
                {
                    "id": document.id,
                    "name": document.original_name,
                    "version": document.version,
                    "drawing_number": document.drawing_number,
                }
                for document in documents
            ]
    return reused


def record_payload(
    record: AcceptanceRecord, db: Optional[Session] = None
) -> Dict[str, Any]:
    request = getattr(record, "request", None)
    request_updated = _as_utc(record.request_updated_at)
    current_updated = _as_utc(request.updated_at) if request is not None else None
    stale = bool(request_updated and current_updated and current_updated > request_updated)
    warning = None
    if stale:
        warning = (
            "PYC đã thay đổi sau khi BBNT này được tạo. BBNT không tự sửa; "
            "hãy xem lại và tạo revision nếu cần."
        )
    return {
        "id": record.id,
        "project_id": record.project_id,
        "request_id": record.request_id,
        "number": record.number,
        "status": record.status,
        "result": record.result,
        "revision": record.revision,
        "supersedes_id": record.supersedes_id,
        "request_updated_at": record.request_updated_at,
        "stale": stale,
        "stale_warning": warning,
        "reused": _reuse_payload(db, record, request),
        "confirmer_id": record.confirmer_id,
        "confirmed_at": record.confirmed_at,
        "record_date": record.record_date,
        "start_time": record.start_time,
        "end_time": record.end_time,
        "design_compliance": record.design_compliance,
        "technical_compliance": record.technical_compliance,
        "other_notes": record.other_notes,
        "conclusion_note": record.conclusion_note,
        "participants": participants_payload(record),
        "checklist": checklist_payload(record),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def preview_request(
    db: Session, project_id: str, request_id: str
) -> Dict[str, Any]:
    request = get_request(db, project_id, request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC trong công trình", "request_not_found")
    return {
        "kind": "pyc",
        "source_id": request.id,
        "cells": {"PYC": _json_safe(_pyc_replacements(request))},
        "warnings": [],
        "stale": False,
    }


def preview_record(
    db: Session, project_id: str, record_id: str
) -> Dict[str, Any]:
    record = get_record(db, project_id, record_id)
    if record is None:
        raise AcceptanceError(404, "Không tìm thấy BBNT trong công trình", "record_not_found")
    request = db.get(AcceptanceRequest, record.request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC của BBNT", "request_not_found")
    payload = record_payload(record, db)
    view = _record_request_view(record, request)
    warnings = [payload["stale_warning"]] if payload.get("stale_warning") else []
    if record.status != "confirmed":
        warnings.append("BBNT chưa được người có quyền xác nhận; chưa thể xuất chính thức.")
    return {
        "kind": "bbnt",
        "source_id": record.id,
        "cells": {
            "PYC": _json_safe(_pyc_replacements(view)),
            "BBNT": _json_safe(_bbnt_replacements(record, view)),
        },
        "warnings": warnings,
        "stale": bool(payload.get("stale")),
    }


def work_item_history(
    db: Session, project_id: str, work_item_id: str
) -> Dict[str, Any]:
    if _SharedWorkItem is not None:
        item = db.get(_SharedWorkItem, work_item_id)
        if item is None or item.project_id != project_id:
            raise AcceptanceError(404, "Công việc không thuộc công trình này", "work_item_not_found")
    requests = list(
        db.scalars(
            select(AcceptanceRequest)
            .where(
                AcceptanceRequest.project_id == project_id,
                AcceptanceRequest.work_item_id == work_item_id,
            )
            .order_by(AcceptanceRequest.updated_at.desc())
        ).all()
    )
    request_ids = [item.id for item in requests]
    records = (
        list(
            db.scalars(
                select(AcceptanceRecord)
                .where(
                    AcceptanceRecord.project_id == project_id,
                    AcceptanceRecord.request_id.in_(request_ids),
                )
                .order_by(AcceptanceRecord.updated_at.desc())
            ).all()
        )
        if request_ids
        else []
    )
    request_by_id = {item.id: item for item in requests}
    items: List[Dict[str, Any]] = []
    for request in requests:
        items.append(
            {
                "kind": "pyc",
                "id": request.id,
                "number": request.number,
                "status": request.status,
                "revision": request.revision,
                "request_id": request.id,
                "result": None,
                "updated_at": request.updated_at,
            }
        )
    for record in records:
        request = request_by_id.get(record.request_id)
        items.append(
            {
                "kind": "bbnt",
                "id": record.id,
                "number": record.number or (request.number if request else ""),
                "status": record.status,
                "revision": record.revision,
                "request_id": record.request_id,
                "result": record.result,
                "updated_at": record.updated_at,
            }
        )
    items.sort(key=lambda item: _as_utc(item["updated_at"]) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return {"work_item_id": work_item_id, "items": items}


def confirm_record(
    db: Session,
    project_id: str,
    record_id: str,
    payload: ConfirmIn,
    actor_id: Optional[str],
) -> AcceptanceRecord:
    record = get_record(db, project_id, record_id)
    if record is None:
        raise AcceptanceError(404, "Không tìm thấy BBNT trong công trình", "record_not_found")
    if record.status == "confirmed":
        raise AcceptanceError(409, "BBNT đã được xác nhận", "record_already_confirmed")
    if not actor_id:
        raise AcceptanceError(403, "Cần người dùng con người để xác nhận", "human_required")
    if not record.checklist:
        raise AcceptanceError(422, "BBNT chưa có checklist", "checklist_required")
    unresolved = [item.item for item in record.checklist if item.state not in {"yes", "no"}]
    if unresolved:
        raise AcceptanceError(
            422,
            "Còn mục checklist chưa xác nhận: " + "; ".join(unresolved),
            "checklist_unconfirmed",
        )
    if record.design_compliance not in {"yes", "no"}:
        raise AcceptanceError(422, "Chưa xác nhận so với thiết kế", "design_compliance_required")
    if record.technical_compliance not in {"yes", "no"}:
        raise AcceptanceError(422, "Chưa xác nhận so với chỉ dẫn kỹ thuật", "technical_compliance_required")

    note = (payload.conclusion_note or "").strip()
    if payload.result == "approved" and (
        record.design_compliance != "yes" or record.technical_compliance != "yes"
    ):
        raise AcceptanceError(
            422, "Không thể kết luận đồng ý khi có mục chất lượng không đạt", "result_inconsistent"
        )
    if payload.result in {"conditional", "rejected"} and not note:
        raise AcceptanceError(
            422, "Kết luận có điều kiện/từ chối phải ghi rõ lý do", "conclusion_note_required"
        )

    record.status = "confirmed"
    record.result = payload.result
    record.conclusion_note = note or None
    record.confirmer_id = actor_id
    record.confirmed_at = datetime.now(timezone.utc)
    record.updated_at = record.confirmed_at
    # Status changes are part of the record workflow, not a PYC edit.  Use a
    # Core UPDATE with an explicit old updated_at so the ORM onupdate hook does
    # not make the request look stale merely because it was confirmed.
    db.execute(
        update(AcceptanceRequest)
        .where(AcceptanceRequest.id == record.request_id)
        .values(
            status="submitted",
            updated_at=record.request_updated_at or record.confirmed_at,
        )
    )
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="confirm",
        entity="AcceptanceRecord",
        entity_id=record.id,
        detail={"result": record.result, "confirmer_id": actor_id},
    )
    db.commit()
    db.refresh(record)
    return record


def _number_value(number: str) -> object:
    text = (number or "").strip()
    if text.isdigit() and not (len(text) > 1 and text.startswith("0")):
        return int(text)
    return text


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "document"


def _pyc_replacements(request: AcceptanceRequest) -> Dict[str, object]:
    content = (request.content or "").strip()
    subject = (request.subject or "").strip()
    if content and subject:
        content_text = f"{content} tại  {subject}"
    else:
        content_text = content or subject or None
    return {
        "C1": f"DỰ ÁN: {request.project_name or ''}",
        "C2": f"CHỦ ĐẦU TƯ: {request.client or ''}",
        "C3": f"ĐỊA ĐIỂM: {request.project_location or ''}",
        "B6": _number_value(request.number),
        "F6": request.request_date,
        "B7": request.location or "",
        "B10": request.request_date,
        "D10": request.inspection_time or "",
        "E10": content_text,
        "H10": "☑" if request.field == "construction" else "□",
        "I10": "☑" if request.field == "electric" else "□",
        "K10": "☑" if request.field == "mechanical" else "□",
        "D14": "☑" if request.urgency == "normal" else "□",
        "D15": "☑" if request.urgency == "urgent" else "□",
        "D16": "☑" if request.urgency == "very_urgent" else "□",
        "A20": request.requested_by_name or "",
        "E20": request.supervisor_name or "",
        "H20": request.investor_name or "",
    }


def _role_participants(record: AcceptanceRecord, role: str) -> List[AcceptanceParticipant]:
    if role == "contractor":
        # A requester profile fills the contractor signature slot on the form.
        return [item for item in record.participants if item.role in {"contractor", "requester"}]
    return [item for item in record.participants if item.role == role]


def _org_label(prefix: str, value: Optional[str]) -> str:
    value = (value or "").strip()
    return f"{prefix} {value}".rstrip()


def _participation_cells(record: AcceptanceRecord, request: AcceptanceRequest) -> Dict[str, object]:
    slots = {
        # The primary template row comes first so a single participant lands in
        # the visible row that already carries the template style.
        "investor": (("B10", "D10"), ("B9", "D9")),
        "supervisor": (("B12", "D12"), ("B13", "D13")),
        "contractor": (("B15", "D15"), ("B16", "D16")),
    }
    values: Dict[str, object] = {}
    for role, role_slots in slots.items():
        people = _role_participants(record, role)
        for index, (name_cell, position_cell) in enumerate(role_slots):
            person = people[index] if index < len(people) else None
            values[name_cell] = person.person_name if person else ""
            values[position_cell] = (person.position or "") if person else ""
    return values


def _quality_line(prefix: str, yes_label: str, no_label: str, state: Optional[str]) -> str:
    return (
        f"{prefix}                              {yes_label}      "
        f"{'☑' if state == 'yes' else '□'}"
        f"                                {no_label}     "
        f"{'☑' if state == 'no' else '□'}                "
    )


def _conclusion_cells(record: AcceptanceRecord) -> Dict[str, object]:
    base = "   Đồng ý nghiệm thu, cho triển khai các công việc tiếp theo "
    note = (record.conclusion_note or "").strip()
    if record.result == "approved":
        return {
            "A36": base + "☑",
            "A37": "   Đồng ý nghiệm thu với điều kiện: ",
        }
    if record.result == "conditional":
        return {
            "A36": base + "□",
            "A37": f"   Đồng ý nghiệm thu với điều kiện: {note} ☑",
        }
    if record.result == "rejected":
        return {
            "A36": base + "□",
            "A37": f"   Không đồng ý nghiệm thu. Lý do: {note}",
        }
    return {
        "A36": base + "□",
        "A37": "   Đồng ý nghiệm thu với điều kiện: ",
    }


def _bbnt_replacements(record: AcceptanceRecord, request: AcceptanceRequest) -> Dict[str, object]:
    investor = _role_participants(record, "investor")
    supervisor = _role_participants(record, "supervisor")
    contractor = _role_participants(record, "contractor")
    investor_org = (investor[0].organization if investor else None) or request.investor_org
    supervisor_org = (supervisor[0].organization if supervisor else None) or request.supervisor_org
    contractor_org = (contractor[0].organization if contractor else None) or request.contractor_org

    values: Dict[str, object] = {
        "B1": f"DỰ ÁN: {request.project_name or ''}",
        "B2": f"CHỦ ĐẦU TƯ: {request.client or ''}",
        "B3": f"ĐỊA ĐIỂM: {request.project_location or ''}",
        "B5": _number_value(request.number),
        "D5": record.record_date,
        "B6": request.location or "",
        "A8": _org_label("Đại diện Chủ đầu tư:", investor_org),
        "A11": _org_label("Đại diện tư vấn giám sát:", supervisor_org),
        "A14": _org_label("Đại diện đơn vị thi công:", contractor_org),
        "B18": record.start_time or "",
        "B19": record.end_time or "",
        "D18": record.record_date,
        "D19": record.record_date,
        "A32": _quality_line(
            "So với thiết kế:", "Đảm bảo", "Không đảm bảo", record.design_compliance
        ),
        "A33": _quality_line(
            "So với yêu cầu, chỉ dẫn kỹ thuật:",
            "Đạt yêu cầu",
            "Không đạt yêu cầu",
            record.technical_compliance,
        ),
        "A34": "Ý kiến khác (nếu có)" + (f": {record.other_notes.strip()}" if record.other_notes else ""),
    }
    values.update(_participation_cells(record, request))
    values.update(_conclusion_cells(record))

    signature_names = [
        investor[0].person_name if investor else "",
        supervisor[0].person_name if supervisor else "",
        contractor[0].person_name if contractor else "",
    ]
    values["A43"] = "      " + "".join(name.ljust(48) for name in signature_names[:2]) + signature_names[2]

    checklist = list(record.checklist)[:7]
    for index in range(7):
        row = 24 + index
        item = checklist[index] if index < len(checklist) else None
        values[f"D{row}"] = "☑" if item is not None and item.state == "yes" else "□"
        values[f"E{row}"] = "☑" if item is not None and item.state == "no" else "□"
    return values


def _blank_bbnt_replacements() -> Dict[str, object]:
    """Safe blank BBNT sheet for a PYC-only export.

    A PYC export still contains the BBNT sheet in the copied workbook.  Leaving
    the source BBNT values there would retain another project's personnel and
    approval conclusion, so every value-bearing BBNT cell is reset.
    """

    values: Dict[str, object] = {
        "B1": "",
        "B2": "",
        "B3": "",
        "B5": None,
        "D5": None,
        "B6": None,
        "A8": "Đại diện Chủ đầu tư:",
        "A11": "Đại diện tư vấn giám sát:",
        "A14": "Đại diện đơn vị thi công:",
        "B18": None,
        "B19": None,
        "D18": None,
        "D19": None,
        "A32": _quality_line("So với thiết kế:", "Đảm bảo", "Không đảm bảo", None),
        "A33": _quality_line(
            "So với yêu cầu, chỉ dẫn kỹ thuật:",
            "Đạt yêu cầu",
            "Không đạt yêu cầu",
            None,
        ),
        "A34": "Ý kiến khác (nếu có)",
        "A36": "   Đồng ý nghiệm thu, cho triển khai các công việc tiếp theo □",
        "A37": "   Đồng ý nghiệm thu với điều kiện: ",
        "A43": None,
    }
    for coord in (
        "B9", "D9", "B10", "D10", "B12", "D12", "B13", "D13",
        "B15", "D15", "B16", "D16",
    ):
        values[coord] = None
    for row in range(24, 31):
        values[f"D{row}"] = "□"
        values[f"E{row}"] = "□"
    return values


def _libreoffice_binary() -> str:
    """Locate LibreOffice headless or fail with an actionable error."""

    configured = (os.getenv(LIBREOFFICE_ENV) or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        if not candidate.is_absolute():
            found = shutil.which(configured)
            if found:
                return found
        raise AcceptanceError(
            503,
            "Không tìm thấy LibreOffice headless để xuất PDF "
            f"(ACCEPTANCE_LIBREOFFICE={configured})",
            "pdf_converter_unavailable",
        )

    for name in ("libreoffice", "soffice"):
        found = shutil.which(name)
        if found:
            return found
    raise AcceptanceError(
        503,
        "Máy chủ chưa cài LibreOffice headless nên không thể xuất PDF. "
        "Cài LibreOffice hoặc đặt ACCEPTANCE_LIBREOFFICE.",
        "pdf_converter_unavailable",
    )


def _pdf_timeout() -> float:
    raw = os.getenv(PDF_TIMEOUT_ENV, str(DEFAULT_PDF_TIMEOUT))
    try:
        value = float(raw)
    except ValueError:
        return float(DEFAULT_PDF_TIMEOUT)
    return value if value > 0 else float(DEFAULT_PDF_TIMEOUT)


def _convert_workbook_to_pdf(workbook: Path, pdf_path: Path) -> None:
    """Convert an already validated workbook with LibreOffice headless."""

    binary = _libreoffice_binary()
    workdir = pdf_path.parent / f".pdf-{uuid.uuid4().hex}"
    profile = workdir / "profile"
    workdir.mkdir(parents=True, exist_ok=False)
    profile.mkdir(parents=True, exist_ok=True)
    try:
        command = [
            binary,
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(workdir),
            str(workbook.resolve()),
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_pdf_timeout(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AcceptanceError(
                500,
                "LibreOffice chuyển PDF quá thời gian cho phép",
                "pdf_conversion_timeout",
            ) from exc

        produced = workdir / f"{workbook.stem}.pdf"
        if not produced.is_file():
            fallback = sorted(workdir.glob("*.pdf"))
            if len(fallback) == 1:
                produced = fallback[0]
        if not produced.is_file():
            detail = (completed.stderr or completed.stdout or "").strip()[-500:]
            raise AcceptanceError(
                500,
                "LibreOffice không tạo được file PDF" + (f": {detail}" if detail else ""),
                "pdf_conversion_failed",
            )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[-500:]
            raise AcceptanceError(
                500,
                "LibreOffice báo lỗi khi chuyển PDF" + (f": {detail}" if detail else ""),
                "pdf_conversion_failed",
            )
        os.replace(produced, pdf_path)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _ensure_pdf_converter(payload: ExportIn) -> None:
    if payload.format == "pdf":
        _libreoffice_binary()


def _render_export(result: Mapping[str, Any], payload: ExportIn) -> Dict[str, Any]:
    """Return the requested artifact; PDF preserves the validated workbook."""

    if payload.format == "xlsx":
        return dict(result)

    workbook_path = Path(str(result["path"]))
    pdf_path = workbook_path.with_suffix(".pdf")
    _convert_workbook_to_pdf(workbook_path, pdf_path)

    metadata = dict(result.get("metadata") or {})
    metadata["workbook_path"] = str(workbook_path)
    metadata["workbook_sha256"] = str(result["sha256"])
    rendered = dict(result)
    rendered.update(
        path=str(pdf_path),
        sha256=sha256_file(pdf_path),
        size_bytes=pdf_path.stat().st_size,
        format="pdf",
        metadata=metadata,
    )
    return rendered


def _write_export(
    *,
    project_id: str,
    source_id: str,
    kind: str,
    template: Path,
    replacements: Mapping[str, Mapping[str, object]],
    scrub: Mapping[str, Iterable[str]],
    actor_id: Optional[str],
    metadata: Mapping[str, Any],
) -> Dict[str, object]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"{timestamp}_{kind}_{_safe_filename(source_id)}.xlsx"
    out_path = _project_export_dir(project_id, source_id) / filename
    try:
        result = copy_and_fill(template, out_path, replacements, scrub)
    except TemplateError:
        raise
    result["source_id"] = source_id
    result["kind"] = kind
    result["format"] = "xlsx"
    result["metadata"] = dict(metadata)
    return result


def export_request(
    db: Session,
    project_id: str,
    request_id: str,
    payload: ExportIn,
    actor_id: Optional[str],
) -> AcceptanceGeneratedDocument:
    if payload.kind != "pyc":
        raise AcceptanceError(422, "Export từ PYC chỉ hỗ trợ kind=pyc", "export_kind_invalid")
    request = get_request(db, project_id, request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC trong công trình", "request_not_found")
    _ensure_pdf_converter(payload)

    template = validate_template(template_path())
    result = _write_export(
        project_id=project_id,
        source_id=request.id,
        kind="pyc",
        template=template,
        replacements={
            "PYC": _pyc_replacements(request),
            "BBNT": _blank_bbnt_replacements(),
        },
        scrub={"PYC (2)": PYC_HIDDEN_SCRUB, "BB LM bt": BBLM_SCRUB},
        actor_id=actor_id,
        metadata={"number": request.number, "status": request.status},
    )
    result = _render_export(result, payload)
    return _persist_export(db, project_id, actor_id, result, template_sha256=result["template_sha256"])


def export_record(
    db: Session,
    project_id: str,
    record_id: str,
    payload: ExportIn,
    actor_id: Optional[str],
) -> AcceptanceGeneratedDocument:
    record = get_record(db, project_id, record_id)
    if record is None:
        raise AcceptanceError(404, "Không tìm thấy BBNT trong công trình", "record_not_found")
    request = db.get(AcceptanceRequest, record.request_id)
    if request is None:
        raise AcceptanceError(404, "Không tìm thấy PYC của BBNT", "request_not_found")

    if payload.kind == "pyc":
        if not request:
            raise AcceptanceError(404, "Không tìm thấy PYC của BBNT", "request_not_found")
        _ensure_pdf_converter(payload)
        result = _write_export(
            project_id=project_id,
            source_id=request.id,
            kind="pyc",
            template=validate_template(template_path()),
            replacements={
                "PYC": _pyc_replacements(request),
                "BBNT": _blank_bbnt_replacements(),
            },
            scrub={"PYC (2)": PYC_HIDDEN_SCRUB, "BB LM bt": BBLM_SCRUB},
            actor_id=actor_id,
            metadata={"number": request.number, "status": request.status, "via_record_id": record.id},
        )
        result = _render_export(result, payload)
        return _persist_export(
            db, project_id, actor_id, result, template_sha256=result["template_sha256"]
        )

    if payload.kind != "bbnt":
        raise AcceptanceError(422, "kind không hợp lệ", "export_kind_invalid")
    if record.status != "confirmed":
        raise AcceptanceError(
            409,
            "BBNT phải được người có quyền xác nhận trước khi xuất",
            "record_not_confirmed",
        )
    _ensure_pdf_converter(payload)
    view = _record_request_view(record, request)
    result = _write_export(
        project_id=project_id,
        source_id=record.id,
        kind="bbnt",
        template=validate_template(template_path()),
        replacements={"PYC": _pyc_replacements(view), "BBNT": _bbnt_replacements(record, view)},
        scrub={"PYC (2)": PYC_HIDDEN_SCRUB, "BB LM bt": BBLM_SCRUB},
        actor_id=actor_id,
        metadata={
            "number": view.number,
            "status": record.status,
            "result": record.result,
            "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        },
    )
    result = _render_export(result, payload)
    return _persist_export(db, project_id, actor_id, result, template_sha256=result["template_sha256"])


def _persist_export(
    db: Session,
    project_id: str,
    actor_id: Optional[str],
    result: Mapping[str, Any],
    *,
    template_sha256: Optional[str],
) -> AcceptanceGeneratedDocument:
    document = AcceptanceGeneratedDocument(
        project_id=project_id,
        kind=str(result["kind"]),
        source_id=str(result["source_id"]),
        path=str(result["path"]),
        sha256=str(result["sha256"]),
        template_sha256=template_sha256,
        format=str(result.get("format") or "xlsx"),
        created_by=actor_id,
        metadata_json=json.dumps(result.get("metadata") or {}, ensure_ascii=False, default=str),
    )
    db.add(document)
    db.flush()
    _audit(
        db,
        project_id=project_id,
        actor_id=actor_id,
        action="export",
        entity="AcceptanceGeneratedDocument",
        entity_id=document.id,
        detail={
            "kind": document.kind,
            "source_id": document.source_id,
            "sha256": document.sha256,
            "template_sha256": template_sha256,
            "format": document.format,
        },
    )
    db.commit()
    db.refresh(document)
    return document


def list_exports(
    db: Session,
    project_id: str,
    *,
    kind: Optional[str] = None,
    source_id: Optional[str] = None,
) -> List[AcceptanceGeneratedDocument]:
    stmt = select(AcceptanceGeneratedDocument).where(
        AcceptanceGeneratedDocument.project_id == project_id,
        AcceptanceGeneratedDocument.kind.in_(("pyc", "bbnt")),
    )
    if kind:
        stmt = stmt.where(AcceptanceGeneratedDocument.kind == kind)
    if source_id:
        stmt = stmt.where(AcceptanceGeneratedDocument.source_id == source_id)
    return list(
        db.scalars(stmt.order_by(AcceptanceGeneratedDocument.generated_at.desc())).all()
    )


def get_export(
    db: Session, project_id: str, export_id: str
) -> Optional[AcceptanceGeneratedDocument]:
    return db.scalar(
        select(AcceptanceGeneratedDocument).where(
            AcceptanceGeneratedDocument.project_id == project_id,
            AcceptanceGeneratedDocument.id == export_id,
            AcceptanceGeneratedDocument.kind.in_(("pyc", "bbnt")),
        )
    )
