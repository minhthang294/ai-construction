"""Read-only catalogue of main construction steps.

The stage catalogue contains every priced item, repeated per design group and
with t-variants.  Site pickers only need the main construction flow, split by
component type.  Pattern rules live here so the map labels, the Zalo summary
and every picker use the same names.

A definition matches at most one rule: hidden minor items are checked first,
then the main steps in construction order.
"""

from __future__ import annotations

import unicodedata
from typing import Iterable

COMPONENT_TYPES = ("pile", "beam")

_MINOR = {
    "pile": (
        ("hút nước", ("hut nuoc",)),
        ("thợ lặn", ("tho lan",)),
        ("vận chuyển đổ thải", ("van chuyen do thai",)),
        ("vệ sinh bằng nước", ("ve sinh bang nuoc",)),
        ("đục hà bám", ("duc ha bam",)),
        ("keo gắn cấy", ("keo gan cay", "keo gan cay thep")),
        ("đường hàn", ("duong han",)),
        ("trám vá", ("tram va", "tram vao")),
        ("dữ liệu demo", ("demo",)),
    ),
    "beam": (
        ("bao tải", ("bao tai",)),
        ("vận chuyển đổ thải", ("van chuyen do thai",)),
        ("keo gắn cấy", ("keo gan cay",)),
        ("đường hàn", ("duong han",)),
        ("trám phẳng/trám lỗ", ("tram ",)),
    ),
}

# (key, label, order, match substrings on the accent-free lowercase name)
_MAIN = {
    "pile": (
        ("pile-derust", "Tẩy gỉ cốt thép", 2, ("tay gi",)),
        ("pile-demolish", "Đục bê tông", 1, ("duc be tong",)),
        ("pile-clean", "Vệ sinh bề mặt", 3,
         ("ve sinh", "mai tao phang", "mai phang", "mai ve sinh")),
        ("pile-rebar", "Bổ sung/khoan cấy cốt thép", 4,
         ("cot thep bo sung", "khoan lo", "khoan cay", "thay the, bo sung cot thep")),
        ("pile-epoxy", "Quét epoxy", 5, ("quet epoxy",)),
        ("pile-sand", "Rắc cát tạo nhám", 6, ("rac cat", "phu cat")),
        ("pile-shell", "Lắp vỏ composite", 7,
         ("lap tam vo composite", "lap vo composite", "quet keo hm-500",
          "lo khoan 3,5", "dinh rut nhom")),
        ("pile-grout", "Bơm vữa không co ngót", 8, ("vua khong co ngot",)),
        ("pile-carbon", "Dán sợi carbon", 9,
         ("dan uot soi carbon", "dan soi carbon")),
        ("pile-paint", "Sơn bảo vệ", 10, ("son bao ve", "he son bao ve")),
    ),
    "beam": (
        ("beam-derust", "Tẩy gỉ cốt thép", 2, ("tay gi",)),
        ("beam-demolish", "Đục bê tông", 1, ("duc be tong", "duc lo")),
        ("beam-clean", "Vệ sinh bề mặt", 3, ("ve sinh", "mai ve sinh")),
        ("beam-rebar", "Bổ sung/khoan cấy cốt thép", 4,
         ("cot thep bo sung", "khoan lo", "thay the, bo sung cot thep")),
        ("beam-epoxy", "Quét epoxy", 5, ("quet epoxy", "phu epoxy")),
        ("beam-sand", "Rắc cát tạo nhám", 6, ("rac cat", "phu cat")),
        ("beam-formwork", "Ván khuôn", 7, ("van khuon",)),
        ("beam-grout", "Đổ/bơm vữa", 8,
         ("vua khong co ngot", "quet chat dinh bam", "quet dinh bam", "sumen latex")),
        ("beam-frp", "Dán sợi thủy tinh", 9,
         ("dan tam soi thuy tinh", "tam soi thuy tinh")),
        ("beam-paint", "Sơn bảo vệ", 10, ("son bao ve", "he son bao ve")),
    ),
}


def _normalise(name: str) -> str:
    text = unicodedata.normalize("NFD", (name or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.replace("đ", "d").strip()


def classify(component_type: str, name: str) -> tuple[str | None, str | None]:
    """Return ``(main work key, hidden reason)``; both None when unmapped."""
    normalised = _normalise(name)
    for reason, patterns in _MINOR.get(component_type, ()):
        if any(pattern in normalised for pattern in patterns):
            return None, reason
    for key, _label, _order, patterns in _MAIN.get(component_type, ()):
        if any(pattern in normalised for pattern in patterns):
            return key, None
    return None, None


def main_work_label(component_type: str, name: str) -> str | None:
    key, _hidden = classify(component_type, name)
    if not key:
        return None
    return next(
        label for work_key, label, _order, _patterns in _MAIN[component_type]
        if work_key == key
    )


def build_main_works(definitions: Iterable) -> dict:
    """Group project definitions into the ordered main-work catalogue.

    ``definitions`` are ORM rows (or any object) with ``id``,
    ``component_type`` and ``name``.  Hidden minor items and definitions that
    match no rule are reported separately so the gap is visible.
    """
    works: dict[tuple[str, str], dict] = {}
    hidden: list[dict] = []
    unmapped: list[dict] = []
    for definition in definitions:
        component_type = definition.component_type
        key, hidden_reason = classify(component_type, definition.name)
        if hidden_reason:
            hidden.append({
                "id": definition.id,
                "component_type": component_type,
                "name": definition.name,
                "reason": hidden_reason,
            })
            continue
        if key is None:
            unmapped.append({
                "id": definition.id,
                "component_type": component_type,
                "name": definition.name,
            })
            continue
        meta = next(
            item for item in _MAIN[component_type] if item[0] == key
        )
        entry = works.setdefault((component_type, key), {
            "key": key,
            "label": meta[1],
            "component_type": component_type,
            "order": meta[2],
            "stage_definition_ids": [],
        })
        entry["stage_definition_ids"].append(definition.id)

    ordered = sorted(
        works.values(),
        key=lambda item: (
            COMPONENT_TYPES.index(item["component_type"]),
            item["order"],
            item["key"],
        ),
    )
    return {"works": ordered, "hidden": hidden, "unmapped": unmapped}
