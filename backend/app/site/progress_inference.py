"""Read-time completion inference for reviewed DAP construction stages.

Only the DAP stage families listed in ``scripts/order_dap_stages.py`` are
eligible.  Dependencies are explicit phase edges matched by component type and
stage name, never by the stored display position.  A stage is inferred from a
successor only when that successor has an actual latest event with status
``COMPLETED`` in the same repair scope.  Nothing here writes progress events.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

_JACKET_LABEL = "lắp tấm vỏ composite tiền chế"
_JACKET_SOURCE = "tấm vỏ composite tiền chế sợi carbon"

# Reviewed DAP display sequence (mirrors scripts/order_dap_stages.py).  Each
# tuple is one phase; alternatives inside a phase are parallel labels, so only
# phase-to-phase edges are dependencies.
_DAP_PHASES: Dict[str, Tuple[Tuple[str, ...], ...]] = {
    "pile": (
        ("đục hà bám", "thợ lặn phục vụ"),
        ("đục bê tông",),
        ("tẩy gỉ", "vệ sinh bề mặt cọc sau khi đục", "vệ sinh bề mặt sau khi đục"),
        ("khoan lỗ d30", "keo gắn cấy thép", "cốt thép bổ sung", "đường hàn"),
        ("mài tạo phẳng và vệ sinh bề mặt cọc", "quét epoxy hm-180", "rắc cát"),
        ("vệ sinh bằng nước sạch", "vệ sinh bề mặt cọc trong phạm vi 50"),
        (_JACKET_LABEL,),
        ("lỗ khoan 3,5", "quét keo hm-500", "đinh rút"),
        ("hút nước khỏi vỏ",),
        ("vữa không co ngót",),
        ("trám vá đầu cọc",),
        (
            "mài tạo phẳng và vệ sinh trong phạm vi dán sợi",
            "mài phẳng và vệ sinh vùng dán sợi",
            "trám vá trong phạm vi dán sợi",
            "trám vá vùng dán sợi",
        ),
        (
            "dán ướt sợi carbon dày 1 mm tấm t1",
            "dán ướt sợi carbon dày 1 mm tấm t2",
            "dán ướt sợi carbon dày 1 mm tấm t3",
        ),
        ("hệ sơn bảo vệ", "sơn bảo vệ"),
        ("vận chuyển đổ thải",),
    ),
    "beam": (
        ("đục bê tông",),
        ("vệ sinh bề mặt", "tẩy gỉ"),
        (
            "khoan lỗ gắn thép",
            "keo gắn cấy cốt thép",
            "cốt thép bổ sung",
            "thay thế, bổ sung cốt thép",
            "đường hàn",
        ),
        (
            "quét epoxy bám dính",
            "quét epoxy hm-180c3p hoặc tương đương, 0,8",
            "quét dính bám sumen latex",
        ),
        ("rắc cát", "phủ cát", "trám sumen mortar"),
        ("ván khuôn", "đục lỗ 100", "quét chất dính bám bê tông cũ và mới trong lỗ"),
        ("vữa không co ngót",),
        ("trám lỗ", "trám phẳng đáy dầm"),
        (
            "mài vệ sinh bê tông trong",
            "trám phẳng bằng sumendur80",
            "trám phẳng sumendur80 trong vùng dán sợi",
        ),
        (
            "dán tấm sợi thủy tinh 0,635 mm lớp 1",
            "tấm sợi thủy tinh dày 0,635 mm lớp 1",
            "dán tấm sợi thủy tinh 0,635 mm lớp 2",
            "tấm sợi thủy tinh dày 0,635 mm lớp 2",
        ),
        (
            "mài vệ sinh ngoài vùng",
            "mài vệ sinh trong vùng quét epoxy",
            "trám phẳng ngoài vùng",
            "trám phẳng sumendur80 bằng 5%",
        ),
        (
            "hệ sơn bảo vệ",
            "sơn bảo vệ",
            "quét epoxy hm-180c3p hoặc tương đương bảo vệ dầm",
            "quét epoxy bảo vệ",
        ),
        ("vận chuyển đổ thải", "bao tải"),
    ),
}

_DAP_CODE_PREFIX = "DAP-"

# Explicit reviewed prerequisite edges as (later phase, earlier phase), zero
# based.  Service/cleanup phases (diver service, disposal/bagging) are not
# completion conditions of the phase before them, so those edges are absent.
_DAP_DEPENDENCY_PHASES: Dict[str, Tuple[Tuple[int, int], ...]] = {
    "pile": (
        (1, 0),
        (2, 1),
        (3, 2),
        (4, 3),
        (5, 4),
        (6, 5),
        (7, 6),
        (8, 7),
        (9, 8),
        (10, 9),
        (11, 10),
        (12, 11),
        (13, 12),
    ),
    "beam": (
        (1, 0),
        (2, 1),
        (3, 2),
        (4, 3),
        (5, 4),
        (6, 5),
        (7, 6),
        (8, 7),
        (9, 8),
        (10, 9),
        (11, 10),
    ),
}

# These are tracked/measured activities, not physical prerequisites.
_NON_INFERABLE_PREFIXES = ("thợ lặn phục vụ", "vận chuyển đổ thải", "bao tải")


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def _phase_index(component_type: str, name: str) -> Optional[int]:
    phases = _DAP_PHASES.get(component_type)
    if not phases:
        return None
    normalized = _normalize(name)
    if normalized.startswith(_JACKET_SOURCE):
        normalized = _JACKET_LABEL
    for index, prefixes in enumerate(phases):
        if any(normalized.startswith(prefix) for prefix in prefixes):
            return index
    return None


def _timestamp(value: Optional[datetime]) -> float:
    if value is None:
        return float("-inf")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _completed_source(
    successors: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    candidates = [
        item
        for item in successors
        if item.get("status") == "COMPLETED" and item.get("latest_event_at")
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (_timestamp(item.get("latest_event_at")), str(item["id"])),
    )


def apply_inferred_progress(
    component_type: str, stages: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Annotate stage dicts with read-time inference; explicit status wins."""
    phase_by_stage: Dict[str, int] = {}
    for stage in stages:
        stage["inferred_from_stage_id"] = None
        stage["inference_conflict"] = False
        if not str(stage.get("code") or "").upper().startswith(_DAP_CODE_PREFIX):
            continue
        index = _phase_index(component_type, str(stage.get("name") or ""))
        if index is not None:
            phase_by_stage[stage["id"]] = index

    dependencies = _DAP_DEPENDENCY_PHASES.get(component_type, ())
    for stage in stages:
        index = phase_by_stage.get(stage["id"])
        if index is None:
            continue
        if any(
            _normalize(str(stage.get("name") or "")).startswith(prefix)
            for prefix in _NON_INFERABLE_PREFIXES
        ):
            continue
        scope_id = stage.get("repair_scope_id")
        if scope_id is None:
            continue
        reachable = {index}
        for later, earlier in dependencies:
            if earlier in reachable:
                reachable.add(later)
        later_phases = reachable - {index}
        successors = [
            item
            for item in stages
            if phase_by_stage.get(item["id"]) in later_phases
            and item.get("repair_scope_id") == scope_id
        ]
        source = _completed_source(successors)
        if source is None:
            continue
        if stage.get("latest_event_at") is None:
            # No actual event exists, so the read projection may show completion
            # without inventing an event or a date.
            stage["status"] = "COMPLETED"
            stage["inferred_from_stage_id"] = source["id"]
        elif stage.get("status") != "COMPLETED":
            # Keep the recorded status; surface the contradiction.
            stage["inference_conflict"] = True
            stage["inferred_from_stage_id"] = source["id"]
    return stages
