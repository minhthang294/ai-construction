"""Role rules for daily-report manpower.

The canonical storage stays ``ManpowerEntry`` rows so reports created before
this feature and every existing export keep working.  The daily report also
exposes a structured "team" projection:

* one named Chỉ huy trưởng;
* zero or more named Kỹ thuật;
* numeric Lái xe / Bảo vệ / Công nhân counts defaulting to ``0``.

Named people are copied to ``ManpowerPreset`` (the project contact directory)
when a report is saved.  Nothing is deleted from the directory automatically.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

CHI_HUY_TRUONG = "Chỉ huy trưởng"
KY_THUAT = "Kỹ thuật"
LAI_XE = "Lái xe"
BAO_VE = "Bảo vệ"
CONG_NHAN = "Công nhân"

ROLE_LABELS: Dict[str, str] = {
    "chi_huy_truong": CHI_HUY_TRUONG,
    "ky_thuat": KY_THUAT,
    "lai_xe": LAI_XE,
    "bao_ve": BAO_VE,
    "cong_nhan": CONG_NHAN,
}
NAMED_ROLES = ("chi_huy_truong", "ky_thuat")
NUMERIC_ROLES = ("lai_xe", "bao_ve", "cong_nhan")

_ALIASES = {
    "chi huy truong": "chi_huy_truong",
    "chi huy truong cong truong": "chi_huy_truong",
    "ky thuat": "ky_thuat",
    "ky thuat cong truong": "ky_thuat",
    "lai xe": "lai_xe",
    "bao ve": "bao_ve",
    "cong nhan": "cong_nhan",
}


def _get(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def normalize_group_name(value: Optional[str]) -> str:
    """Case/accent/spacing-insensitive key used to recognise legacy labels."""

    text = str(value or "").strip().casefold()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


def canonical_role(group_name: Optional[str]) -> Optional[str]:
    """Return the managed role key for a group label, or ``None``.

    Only exact known labels are managed.  Other manpower rows are preserved as
    free-form rows and are never silently reinterpreted.
    """

    return _ALIASES.get(normalize_group_name(group_name))


def is_managed_group(group_name: Optional[str]) -> bool:
    return canonical_role(group_name) is not None


def clean_person_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    return text or None


def _clean_number(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def manpower_team_from_entries(entries: Iterable[Any]) -> Dict[str, Any]:
    """Project stored manpower rows into the structured team shape.

    Numeric role counts are summed when legacy data contains more than one row
    for the same role.  ``None`` counts contribute zero because these roles are
    numeric in the new form.  The original rows remain untouched in ``manpower``.
    """

    team: Dict[str, Any] = {
        "chi_huy_truong": None,
        "ky_thuat": [],
        "lai_xe": 0,
        "bao_ve": 0,
        "cong_nhan": 0,
    }
    engineer_names: set[str] = set()

    for entry in entries:
        role = canonical_role(_get(entry, "group_name"))
        if role == "chi_huy_truong":
            name = clean_person_name(_get(entry, "person_name"))
            if name and team["chi_huy_truong"] is None:
                team["chi_huy_truong"] = name
        elif role == "ky_thuat":
            name = clean_person_name(_get(entry, "person_name"))
            if name and name.casefold() not in engineer_names:
                engineer_names.add(name.casefold())
                team["ky_thuat"].append(name)
        elif role in NUMERIC_ROLES:
            count = _clean_number(_get(entry, "count"))
            if count is not None and count >= 0:
                team[role] += count

    team["ky_thuat"].sort(key=str.casefold)
    return team


def named_contacts_from_entries(entries: Iterable[Any]) -> List[Dict[str, str]]:
    """Return unique named contacts that belong in the project directory."""

    contacts: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        role = canonical_role(_get(entry, "group_name"))
        if role not in NAMED_ROLES:
            continue
        name = clean_person_name(_get(entry, "person_name"))
        if not name:
            continue
        key = (role, name.casefold())
        if key in seen:
            continue
        seen.add(key)
        contacts.append(
            {
                "role": role,
                "group_name": ROLE_LABELS[role],
                "person_name": name,
            }
        )
    return contacts


def team_to_manpower_values(team: Any) -> List[Dict[str, Any]]:
    """Build fixed-role manpower rows from a validated team payload.

    Named roles store ``count=1`` (one person per row) so the existing total
    summary and exports remain meaningful.  Numeric roles always produce a row,
    including an explicit ``0``.
    """

    values: List[Dict[str, Any]] = []

    chief = clean_person_name(_get(team, "chi_huy_truong"))
    if chief:
        values.append(
            {
                "group_name": CHI_HUY_TRUONG,
                "person_name": chief,
                "count": 1,
                "organization_id": None,
            }
        )

    engineers_raw = _get(team, "ky_thuat") or []
    if isinstance(engineers_raw, str):
        engineers_raw = [engineers_raw]
    seen_engineers: set[str] = set()
    for raw_name in engineers_raw:
        name = clean_person_name(raw_name)
        if not name or name.casefold() in seen_engineers:
            continue
        seen_engineers.add(name.casefold())
        values.append(
            {
                "group_name": KY_THUAT,
                "person_name": name,
                "count": 1,
                "organization_id": None,
            }
        )

    for role in NUMERIC_ROLES:
        count = _clean_number(_get(team, role))
        if count is None or count < 0:
            count = 0
        values.append(
            {
                "group_name": ROLE_LABELS[role],
                "person_name": None,
                "count": count,
                "organization_id": None,
            }
        )
    return values


def split_team_and_legacy(items: Sequence[Any]) -> tuple[List[Any], List[Any]]:
    """Split request rows into free-form legacy rows and managed role rows."""

    legacy = [item for item in items if not is_managed_group(_get(item, "group_name"))]
    managed = [item for item in items if is_managed_group(_get(item, "group_name"))]
    return legacy, managed
