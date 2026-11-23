"""Display helpers for per-component design parameters (pile thickness t)."""

from __future__ import annotations

import re
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .component_models import ComponentDesignParameter


def format_parameter_value(value: float) -> str:
    return f"{float(value):g}"


def display_stage_name(name: str, t_values: Iterable[Optional[float]]) -> str:
    """Append the pile thickness to a stage name ending in ``t``.

    ``Đục bê tông om vỡ dày trung bình t`` becomes ``... t = 3 cm``.  If several
    different values are present the result is a range.  Missing values are
    explicit, never guessed.
    """

    if not name:
        return name
    folded = name.casefold()
    if folded.endswith(" t"):
        base = name[:-2].rstrip()
    elif "trung bình t" in folded:
        base = re.sub(r"trung bình t", "trung bình", name, count=1, flags=re.IGNORECASE).rstrip()
    else:
        return name
    raw_values = list(t_values)
    values = sorted({round(float(value), 4) for value in raw_values if value is not None})
    has_missing = any(value is None for value in raw_values)
    if not values:
        return f"{base} t (chưa có số liệu)"
    suffix = " (một số chưa có số liệu)" if has_missing else ""
    if len(values) == 1:
        return f"{base} t = {format_parameter_value(values[0])} cm{suffix}"
    return (
        f"{base} t = {format_parameter_value(values[0])}–"
        f"{format_parameter_value(values[-1])} cm{suffix}"
    )


def load_t_values(db: Session, component_ids: Iterable[str]) -> dict[str, float]:
    ids = list(dict.fromkeys(component_ids))
    if not ids:
        return {}
    rows = db.execute(
        select(ComponentDesignParameter.component_id, ComponentDesignParameter.value).where(
            ComponentDesignParameter.component_id.in_(ids),
            ComponentDesignParameter.name == "t_cm",
        )
    ).all()
    return {component_id: float(value) for component_id, value in rows}


def load_parameters(db: Session, component_ids: Iterable[str]) -> dict[str, list[dict]]:
    ids = list(dict.fromkeys(component_ids))
    if not ids:
        return {}
    out: dict[str, list[dict]] = {}
    for row in db.scalars(
        select(ComponentDesignParameter)
        .where(ComponentDesignParameter.component_id.in_(ids))
        .order_by(ComponentDesignParameter.component_id, ComponentDesignParameter.name)
    ):
        out.setdefault(row.component_id, []).append(
            {
                "name": row.name,
                "value": row.value,
                "unit": row.unit,
                "source_drawing": row.source_drawing,
                "source_page": row.source_page,
                "source_row": row.source_row,
                "source_file_hash": row.source_file_hash,
            }
        )
    return out
