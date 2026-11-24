#!/usr/bin/env python3
"""Import the reviewed Phân đoạn 1 acceptance history from the private workbook.

Preview never writes. ``--commit`` creates only draft/confirmed PYC and BBNT
records that the workbook itself shows, links matching components/stages, and
writes one audit entry. It never invents numbers or dates, never edits the
workbook, and is idempotent on ``sheet=DM; row=...; number=...``.

Examples:
  python scripts/import_acceptance_workbook.py \
    --database sqlite:///data/app.db \
    --project "DAP - PD1 da duyet (du lieu thuc te)" \
    --xlsx "YCNT và BBNT.19.10.xlsx" \
    --reconciliation data/storage/design-review/DAP-doi-chieu-tien-do-YCNT-BBNT-19.10.xlsx \
    --segment 1

  # add --commit to write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.acceptance.models import (  # noqa: E402
    AcceptanceRecord,
    AcceptanceRequest,
    ComponentAcceptanceLink,
)
from app.core.component_models import (  # noqa: E402
    ComponentAlias,
    ComponentStage,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.models import AuditLog, Project, ProjectMember, User  # noqa: E402

MARKER = "[import_acceptance_workbook]"
DM_SHEET = "DM"
FIRST_DATA_ROW = 6
MAX_VALID_YEAR = 2100
MIN_VALID_YEAR = 2000

# Trigger -> stage-name prefixes. Longest trigger per group wins, so a more
# specific line such as "... bề mặt cọc (phần dán sợi)" is not also matched by
# the plain "mài tạo phẳng" rule.
STAGE_RULES: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {
    "duc": [
        ("đục bỏ bê tông om vỡ", ("đục bê tông om vỡ",)),
        ("đục bê tông om vỡ", ("đục bê tông om vỡ",)),
    ],
    "van_chuyen": [("vận chuyển đổ thải", ("vận chuyển đổ thải",))],
    "tay_gi": [("tẩy gỉ cốt thép", ("tẩy gỉ cốt thép",))],
    "ve_sinh": [
        ("vệ sinh bề mặt bê tông", ("vệ sinh bề mặt bê tông sau khi đục",)),
        ("vệ sinh bề mặt cọc", ("vệ sinh bề mặt cọc sau khi đục",)),
    ],
    "mai": [
        (
            "mài tạo phẳng và vệ sinh bề mặt cọc (phần dán sợi)",
            ("mài tạo phẳng và vệ sinh trong phạm vi dán sợi",),
        ),
        (
            "mài tạo phẳng và vệ sinh bề mặt cọc",
            ("mài tạo phẳng và vệ sinh bề mặt cọc",),
        ),
        ("mài vệ sinh bề mặt", ("mài vệ sinh",)),
    ],
    "quet_epoxy": [
        ("quét epoxy bám dính", ("quét epoxy bám dính",)),
        (
            "vệ sinh quét keo epoxy",
            ("quét epoxy", "quét keo epoxy"),
        ),
        ("quét epoxy", ("quét epoxy",)),
    ],
    "quet_dinh_bam": [("quét dính bám", ("quét chất dính bám",))],
    "rac_cat": [("rắc cát", ("rắc cát", "phủ cát"))],
    "tam_vo": [
        ("lắp đặt tấm vỏ", ("lắp tấm vỏ", "tấm vỏ composite")),
        ("lắp tấm vỏ", ("lắp tấm vỏ", "tấm vỏ composite")),
        ("tấm vỏ composite", ("lắp tấm vỏ", "tấm vỏ composite")),
    ],
    "vua": [("vữa không co ngót", ("vữa không co ngót",))],
    "hut_nuoc": [("hút nước", ("hút nước",))],
    "tram": [
        ("trám vá và dán sợi", ("trám vá trong phạm vi dán sợi", "trám vá vùng dán sợi")),
        ("trám vá đầu cọc", ("trám vá đầu cọc",)),
        ("trám vá lỗ", ("trám lỗ",)),
        ("trám phẳng", ("trám phẳng",)),
        ("trám lỗ", ("trám lỗ",)),
        ("trám vá", ("trám vá",)),
    ],
    "dan_carbon": [
        ("dán sợi cacbon", ("dán ướt sợi carbon", "tấm sợi carbon")),
        ("dán sợi carbon", ("dán ướt sợi carbon", "tấm sợi carbon")),
        ("dán vải sợi carbon", ("dán ướt sợi carbon", "tấm sợi carbon")),
    ],
    "dan_thuy_tinh": [
        ("dán sợi thủy tinh", ("dán tấm sợi thủy tinh", "tấm sợi thủy tinh")),
    ],
    "son": [
        ("sơn chống tia uv", ("hệ sơn", "sơn bảo vệ", "sơn chống")),
        ("sơn chống uv", ("hệ sơn", "sơn bảo vệ", "sơn chống")),
    ],
    "cot_thep": [
        ("thay thế, bổ sung cốt thép", ("thay thế, bổ sung cốt thép",)),
        ("thay thế bổ sung cốt thép", ("thay thế, bổ sung cốt thép",)),
        ("cốt thép bổ sung", ("cốt thép bổ sung",)),
    ],
    "van_khuon": [
        ("tháo dỡ ván khuôn", ("ván khuôn",)),
        ("lắp dựng ván khuôn", ("ván khuôn",)),
    ],
    "khoan": [("khoan cấy", ("khoan",)), ("khoan lỗ", ("khoan",))],
    "duc_lo": [("đục lỗ", ("đục lỗ",))],
}


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").casefold()
    return " ".join(text.split())


def _stage_prefixes(work: str) -> List[str]:
    folded = _fold(work)
    prefixes: List[str] = []
    for rules in STAGE_RULES.values():
        for trigger, names in sorted(rules, key=lambda item: -len(item[0])):
            if _fold(trigger) in folded:
                prefixes.extend(_fold(name) for name in names)
                break
    return list(dict.fromkeys(prefixes))


def _name_signature(name: str) -> str:
    folded = re.sub(r"[^a-z0-9 ]", " ", _fold(name))
    tokens = folded.split()
    leading = {"lap", "dan", "quet", "he", "son", "mai", "duc", "tram", "thao", "tay", "rac", "van", "hut", "cat"}
    while tokens and tokens[0] in leading:
        tokens.pop(0)
    return " ".join(tokens[:3])


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _number_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit() and len(text) < 3:
        return text.zfill(2)
    return text


def _as_date(value: object) -> Optional[date]:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value if MIN_VALID_YEAR <= value.year <= MAX_VALID_YEAR else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
        return parsed if MIN_VALID_YEAR <= parsed.year <= MAX_VALID_YEAR else None
    return None


def _is_formula(value: object) -> bool:
    return isinstance(value, str) and value.startswith("=")


@dataclass
class RowPlan:
    row: int
    number: str
    work: str
    target: str
    location: str
    yc_date: Optional[date]
    nt_date: Optional[date]
    nt_formula: bool
    in_segment_hint: bool = False
    code_pairs: List[Tuple[str, Optional[str]]] = field(default_factory=list)
    links: List[Tuple[str, str, Optional[str]]] = field(default_factory=list)
    unmatched_codes: List[str] = field(default_factory=list)
    stage_missing: List[str] = field(default_factory=list)
    scope_unverified: List[str] = field(default_factory=list)
    duplicate: bool = False
    reasons: List[str] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return not self.reasons


@dataclass
class DbContext:
    session: Session
    project: Project
    actor: User
    target_segments: List[Segment]
    components: List[StructuralComponent]
    exact: Dict[str, List[StructuralComponent]]
    aliases: Dict[str, List[StructuralComponent]]
    stages: Dict[str, List[Tuple[ComponentStage, StageDefinition, Optional[RepairScope]]]]
    reconciliation: Dict[Tuple[int, str], List[str]]


def _load_components(db: Session, project_id: str, target_ids: Iterable[str]):
    components = list(
        db.scalars(
            select(StructuralComponent).where(
                StructuralComponent.project_id == project_id,
                StructuralComponent.segment_id.in_(list(target_ids)),
            )
        ).all()
    )
    exact: Dict[str, List[StructuralComponent]] = defaultdict(list)
    for component in components:
        for value in (component.canonical_code, component.raw_code):
            key = str(value or "").strip().upper()
            if key:
                exact[key].append(component)
    aliases: Dict[str, List[StructuralComponent]] = defaultdict(list)
    by_id = {component.id: component for component in components}
    for alias in db.scalars(
        select(ComponentAlias).where(ComponentAlias.project_id == project_id)
    ).all():
        component = by_id.get(alias.component_id)
        if component is None:
            continue
        key = str(alias.alias or "").strip().upper()
        if key:
            aliases[key].append(component)
            aliases[key.replace("-", "")].append(component)
    stages = defaultdict(list)
    if components:
        rows = db.execute(
            select(ComponentStage, StageDefinition, RepairScope)
            .join(StageDefinition, StageDefinition.id == ComponentStage.stage_definition_id)
            .outerjoin(RepairScope, RepairScope.id == ComponentStage.repair_scope_id)
            .where(ComponentStage.component_id.in_([item.id for item in components]))
        ).all()
        for stage, definition, scope in rows:
            stages[stage.component_id].append((stage, definition, scope))
    return components, exact, aliases, stages


def _resolve_component(
    context: DbContext, code: str, type_hint: Optional[str]
) -> Tuple[Optional[StructuralComponent], bool]:
    key = code.strip().upper()
    candidates = list(context.exact.get(key, []))
    if not candidates:
        candidates = list(context.aliases.get(key, []))
    if not candidates:
        candidates = list(context.aliases.get(key.replace("-", ""), []))
    if type_hint:
        typed = [item for item in candidates if item.type == type_hint]
        if typed:
            candidates = typed
    unique = {item.id: item for item in candidates}
    if len(unique) == 1:
        return next(iter(unique.values())), False
    return None, len(unique) > 1


def _parse_codes(raw: object) -> List[Tuple[str, Optional[str]]]:
    codes: List[Tuple[str, Optional[str]]] = []
    for part in re.split(r"[;,]", str(raw or "")):
        part = part.strip()
        if not part:
            continue
        type_hint: Optional[str] = None
        match = re.match(r"^(cọc|dầm)(\s+phát sinh)?\s+(.+)$", part, re.IGNORECASE)
        if match:
            type_hint = "pile" if match.group(1).casefold() == "cọc" else "beam"
            part = match.group(3).strip()
        if not part or " " in part or not re.search(r"\d", part):
            continue
        if not re.fullmatch(r"[A-Za-z0-9-]+", part):
            continue
        codes.append((part, type_hint))
    return codes


def _read_reconciliation(path: Optional[Path]) -> Dict[Tuple[int, str], List[str]]:
    if path is None or not path.is_file():
        return {}
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if "Đã ghi tiến độ" not in workbook.sheetnames:
            return {}
        sheet = workbook["Đã ghi tiến độ"]
        result: Dict[Tuple[int, str], List[str]] = defaultdict(list)
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None or row[1] is None or row[2] is None:
                continue
            try:
                dm_row = int(row[0])
            except (TypeError, ValueError):
                continue
            code = str(row[1]).strip().upper()
            result[(dm_row, code)].append(str(row[2]).strip())
        return result
    finally:
        workbook.close()


def _row_stage_links(
    context: DbContext,
    plan: RowPlan,
    component: StructuralComponent,
    reconciliation_names: List[str],
) -> Tuple[List[Tuple[str, str, Optional[str]]], List[str], List[str]]:
    rows = context.stages.get(component.id, [])
    links: List[Tuple[str, str, Optional[str]]] = []
    missing: List[str] = []
    unverified: List[str] = []
    if reconciliation_names:
        matches = []
        unresolved = []
        for name in reconciliation_names:
            folded = _fold(name)
            found = [
                (stage, definition, scope)
                for stage, definition, scope in rows
                if (
                    _fold(definition.name) == folded
                    or _fold(definition.name).startswith(folded)
                )
            ]
            if found:
                matches.extend(found)
            else:
                unresolved.append(name)
        for name in unresolved:
            signature = _name_signature(name)
            if not signature:
                continue
            matches.extend(
                (stage, definition, scope)
                for stage, definition, scope in rows
                if signature in _fold(definition.name)
            )
        matches = list({stage.id: (stage, definition, scope) for stage, definition, scope in matches}.values())
    else:
        matches = []
    if not matches:
        prefixes = _stage_prefixes(plan.work)
        matches = [
            (stage, definition, scope)
            for stage, definition, scope in rows
            if any(_fold(definition.name).startswith(prefix) for prefix in prefixes)
        ]
    for stage, definition, scope in matches:
        links.append((component.id, stage.id, stage.repair_scope_id))
        if scope is not None and scope.verification != "VERIFIED":
            unverified.append(f"{component.canonical_code}:{definition.name}")
    if not matches:
        missing.append(component.canonical_code)
    return links, missing, unverified


def _load_rows(path: Path, segment: int) -> Tuple[List[RowPlan], int]:
    values = load_workbook(path, read_only=False, data_only=True)
    formulas = load_workbook(path, read_only=False, data_only=False)
    try:
        if DM_SHEET not in values.sheetnames:
            raise SystemExit(f"Workbook has no {DM_SHEET} sheet: {path}")
        ws = values[DM_SHEET]
        ws_formula = formulas[DM_SHEET]
        rows: List[RowPlan] = []
        skipped_empty = 0
        segment_key = f"phan doan {segment}"
        for row_number in range(FIRST_DATA_ROW, ws.max_row + 1):
            number = _number_text(ws.cell(row_number, 2).value)
            work = _clean_text(ws.cell(row_number, 3).value)
            target = _clean_text(ws.cell(row_number, 4).value)
            location = _clean_text(ws.cell(row_number, 10).value)
            yc_date = _as_date(ws.cell(row_number, 5).value)
            nt_date = _as_date(ws.cell(row_number, 7).value)
            nt_formula = _is_formula(ws_formula.cell(row_number, 7).value)
            if not work and not target:
                skipped_empty += 1
                continue
            in_segment = (
                segment_key in _fold(location)
                or segment_key in _fold(target)
            )
            code_pairs = _parse_codes(target)
            rows.append(
                RowPlan(
                    row=row_number,
                    number=number,
                    work=work,
                    target=target,
                    location=location,
                    yc_date=yc_date,
                    nt_date=nt_date,
                    nt_formula=nt_formula,
                    in_segment_hint=in_segment,
                    code_pairs=code_pairs,
                )
            )
        return rows, skipped_empty
    finally:
        values.close()
        formulas.close()


def _build_plans(
    rows: List[RowPlan],
    context: DbContext,
) -> Tuple[List[RowPlan], int, List[str], List[str]]:
    included: List[RowPlan] = []
    skipped_not_segment = 0
    unmatched_global: List[str] = []
    duplicate_numbers: List[str] = []
    for plan in rows:
        code_pairs = plan.code_pairs
        hint = plan.in_segment_hint
        resolved = []
        for code, type_hint in code_pairs:
            component, ambiguous = _resolve_component(context, code, type_hint)
            if component is None:
                plan.unmatched_codes.append(code + (" (mơ hồ)" if ambiguous else ""))
                unmatched_global.append(code)
            else:
                resolved.append((code, component))
        if not hint:
            skipped_not_segment += 1
            continue
        for code, component in resolved:
            names = context.reconciliation.get((plan.row, code.upper()), [])
            links, missing, unverified = _row_stage_links(
                context, plan, component, names
            )
            plan.links.extend(links)
            plan.stage_missing.extend(missing)
            plan.scope_unverified.extend(unverified)
        included.append(plan)

    counts = Counter(plan.number for plan in included if plan.number)
    duplicate_numbers = sorted(
        [number for number, count in counts.items() if count > 1]
    )
    for plan in included:
        if plan.number and plan.number in duplicate_numbers:
            plan.duplicate = True
            plan.reasons.append("số biên bản trùng")
        if not plan.number:
            plan.reasons.append("thiếu số biên bản")
        if plan.yc_date is None:
            plan.reasons.append("thiếu ngày yêu cầu")
        if plan.nt_date is None:
            plan.reasons.append("thiếu ngày nghiệm thu")
        if plan.yc_date and plan.nt_date and plan.nt_date < plan.yc_date:
            plan.reasons.append("ngày nghiệm thu trước ngày yêu cầu")
        if plan.unmatched_codes:
            plan.reasons.append("mã chưa khớp: " + ", ".join(plan.unmatched_codes))
        if plan.stage_missing:
            plan.reasons.append(
                "công đoạn chưa khớp: " + ", ".join(plan.stage_missing)
            )
        if plan.scope_unverified:
            plan.reasons.append(
                "phạm vi cần xác minh: " + ", ".join(plan.scope_unverified)
            )
        plan.links = sorted(set(plan.links))
    return included, skipped_not_segment, unmatched_global, duplicate_numbers


def _provenance(path: Path, plan: RowPlan, segment: int) -> str:
    return (
        f"{MARKER} sheet={DM_SHEET}; row={plan.row}; number={plan.number}; "
        f"segment={segment}; source={path.name}"
    )


def _existing_request(
    db: Session, project_id: str, plan: RowPlan
) -> Optional[AcceptanceRequest]:
    marker = f"{MARKER} sheet={DM_SHEET}; row={plan.row}; number={plan.number};"
    return db.scalar(
        select(AcceptanceRequest).where(
            AcceptanceRequest.project_id == project_id,
            AcceptanceRequest.notes.contains(marker),
        )
    )


def _load_context(
    db: Session,
    project: Project,
    segment: int,
    reconciliation: Dict[Tuple[int, str], List[str]],
    actor_name: Optional[str],
) -> DbContext:
    zones = list(
        db.scalars(
            select(StructureZone).where(StructureZone.project_id == project.id)
        ).all()
    )
    target_segments = list(
        db.scalars(
            select(Segment).where(
                Segment.zone_id.in_(
                    [
                        zone.id
                        for zone in zones
                        if _fold(zone.name) == "cau chinh"
                    ]
                ),
                Segment.number == segment,
            )
        ).all()
    )
    if not target_segments:
        raise SystemExit(f"No Cầu chính segment {segment} in this project")
    components, exact, aliases, stages = _load_components(
        db, project.id, [item.id for item in target_segments]
    )
    if actor_name:
        actor = db.scalar(
            select(User).where(
                (User.username == actor_name) | (User.id == actor_name)
            )
        )
    else:
        actor = db.scalar(
            select(User)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project.id)
            .order_by(ProjectMember.role.desc())
        )
    if actor is None:
        raise SystemExit(
            "No project user found; pass --actor <username|id> or create a member first"
        )
    return DbContext(
        session=db,
        project=project,
        actor=actor,
        target_segments=target_segments,
        components=components,
        exact=exact,
        aliases=aliases,
        stages=stages,
        reconciliation=reconciliation,
    )


def _print_preview(
    plans: List[RowPlan],
    skipped_not_segment: int,
    unmatched: List[str],
    duplicates: List[str],
    existing: int,
) -> None:
    confirmed = [plan for plan in plans if plan.confirmed]
    review = [plan for plan in plans if not plan.confirmed]
    links = sum(len(plan.links) for plan in plans)
    print("IMPORT PREVIEW (no writes)")
    print(f"  PYC found: {len(plans)}; BBNT found: {len(plans)}")
    print(f"  To create: PYC {len(plans) - existing}, BBNT {len(plans) - existing}; existing: {existing}")
    print(f"  Confirmed: {len(confirmed)}; needs review: {len(review)}")
    print(f"  Component-stage links: {links}")
    print(f"  Rows skipped (not PD1): {skipped_not_segment}")
    print(f"  Unmatched codes: {len(unmatched)}")
    if unmatched:
        print("    " + ", ".join(sorted(set(unmatched))))
    print(f"  Duplicate numbers: {len(duplicates)}")
    if duplicates:
        print("    " + ", ".join(duplicates))
    if review:
        print("  Needs review:")
        for plan in review:
            print(
                f"    DM row {plan.row} (BB {plan.number or '?'}): "
                + "; ".join(plan.reasons)
            )
    print("  Sample rows:")
    for plan in plans[:10]:
        status = "confirmed" if plan.confirmed else "needs_review"
        print(
            f"    DM row {plan.row} | BB {plan.number or '?'} | "
            f"PYC {plan.yc_date} | BBNT {plan.nt_date} | "
            f"{len(plan.links)} links | {status} | {plan.work[:80]}"
        )


def _commit(
    context: DbContext,
    plans: List[RowPlan],
    source: Path,
    segment: int,
) -> Dict[str, int]:
    db = context.session
    created_requests = 0
    created_records = 0
    created_links = 0
    existing = 0
    confirmed = 0
    review = 0
    seen_numbers = set()
    for plan in plans:
        duplicate_number = bool(plan.number and plan.number in seen_numbers)
        if plan.number:
            seen_numbers.add(plan.number)
        if duplicate_number:
            # A duplicate number cannot be stored twice (project+number unique);
            # the first occurrence is imported as a draft and the rest are
            # reported by the preview instead of inventing a suffix.
            existing += 1
            continue
        if _existing_request(db, context.project.id, plan):
            existing += 1
            continue
        if plan.number and db.scalar(
            select(AcceptanceRequest.id).where(
                AcceptanceRequest.project_id == context.project.id,
                AcceptanceRequest.number == f"YC-{plan.number}",
            )
        ):
            existing += 1
            continue
        provenance = _provenance(source, plan, segment)
        notes = provenance + "\n" + ("; ".join(plan.reasons) if plan.reasons else "")
        if plan.nt_formula:
            notes += "\nNgày nghiệm thu trong workbook là công thức; giá trị đã đọc từ file."
        request = AcceptanceRequest(
            project_id=context.project.id,
            number=f"YC-{plan.number}",
            status="submitted" if plan.confirmed else "draft",
            project_name=context.project.name,
            location=plan.location[:500] or None,
            subject=plan.work or None,
            content=(
                f"{plan.work}\nĐối tượng: {plan.target}\nVị trí: {plan.location}"
            ),
            request_date=plan.yc_date,
            field="construction",
            urgency="normal",
            notes=notes,
        )
        record = AcceptanceRecord(
            project_id=context.project.id,
            request=request,
            number=f"NT-{plan.number}",
            revision=1,
            status="confirmed" if plan.confirmed else "draft",
            result="approved" if plan.confirmed else None,
            confirmer_id=context.actor.id if plan.confirmed else None,
            confirmed_at=(
                datetime.combine(plan.nt_date, time(0, 0), tzinfo=timezone.utc)
                if plan.confirmed and plan.nt_date
                else None
            ),
            record_date=plan.nt_date,
            other_notes=notes,
        )
        db.add(request)
        db.add(record)
        db.flush()
        created_requests += 1
        created_records += 1
        if plan.confirmed:
            confirmed += 1
        else:
            review += 1
        for component_id, stage_id, scope_id in plan.links:
            exists = db.scalar(
                select(ComponentAcceptanceLink.id).where(
                    ComponentAcceptanceLink.project_id == context.project.id,
                    ComponentAcceptanceLink.component_id == component_id,
                    ComponentAcceptanceLink.stage_id == stage_id,
                    ComponentAcceptanceLink.scope_id == scope_id,
                    ComponentAcceptanceLink.record_id == record.id,
                )
            )
            if exists:
                continue
            db.add(
                ComponentAcceptanceLink(
                    project_id=context.project.id,
                    component_id=component_id,
                    stage_id=stage_id,
                    scope_id=scope_id,
                    record_id=record.id,
                    created_by=context.actor.id,
                )
            )
            created_links += 1
    if created_requests or created_records:
        detail = {
            "source": source.name,
            "segment": segment,
            "pyc_created": created_requests,
            "bbnt_created": created_records,
            "links_created": created_links,
            "confirmed": confirmed,
            "needs_review": review,
            "existing": existing,
        }
        db.add(
            AuditLog(
                project_id=context.project.id,
                actor_id=context.actor.id,
                action="acceptance_workbook_imported",
                entity="AcceptanceImport",
                entity_id=str(uuid.uuid4()),
                detail=json.dumps(detail, ensure_ascii=False),
            )
        )
    db.commit()
    return {
        "pyc_created": created_requests,
        "bbnt_created": created_records,
        "links_created": created_links,
        "confirmed": confirmed,
        "needs_review": review,
        "existing": existing,
    }


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    return "sqlite:///" + Path(value).resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--xlsx", required=True, type=Path)
    parser.add_argument("--reconciliation", type=Path, default=None)
    parser.add_argument("--segment", type=int, default=1)
    parser.add_argument("--actor", default=None)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    if not args.xlsx.is_file():
        print(f"Workbook not found: {args.xlsx}", file=sys.stderr)
        return 2
    if args.reconciliation is not None and not args.reconciliation.is_file():
        print(f"Reconciliation not found: {args.reconciliation}", file=sys.stderr)
        return 2

    engine = create_engine(_database_url(args.database), future=True)
    with Session(engine, expire_on_commit=False) as db:
        project = db.scalar(select(Project).where(Project.name == args.project))
        if project is None:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        reconciliation = _read_reconciliation(args.reconciliation)
        context = _load_context(
            db, project, args.segment, reconciliation, args.actor
        )
        rows, _skipped_empty = _load_rows(args.xlsx, args.segment)
        plans, skipped, unmatched, duplicates = _build_plans(rows, context)
        existing = sum(
            1 for plan in plans if _existing_request(db, project.id, plan)
        )
        if not args.commit:
            _print_preview(plans, skipped, unmatched, duplicates, existing)
            return 0
        result = _commit(context, plans, args.xlsx, args.segment)
        print("IMPORT COMMITTED")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
