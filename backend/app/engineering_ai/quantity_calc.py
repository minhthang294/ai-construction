"""Deterministic rectangular area/volume calculations from sourced dimensions.

Every input is a :class:`Dimension` with a positive numeric value, an explicit
length unit, a component identity and the citation for the source cell/quote.
The module performs only arithmetic; it never guesses missing geometry.

shortcut: only one rectangular region is supported; add a work-item geometry
rule when drawings show curves, overlaps, layers or changing sections.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple, Union

Number = Union[int, float, Decimal]

_LENGTH_UNIT_TO_M = {
    "mm": Decimal("0.001"),
    "cm": Decimal("0.01"),
    "m": Decimal("1"),
}


class QuantityCalculationError(ValueError):
    """Raised when a quantity cannot be calculated unambiguously."""


@dataclass(frozen=True)
class Dimension:
    """One sourced linear dimension.

    ``component_code`` and ``revision`` are used only to prevent mixing
    dimensions from different members/revisions.  ``citation`` must identify
    the page/cell/quote that supports the number and unit.
    """

    value: Number
    unit: str
    component_code: str
    citation: str
    revision: Optional[str] = None


@dataclass(frozen=True)
class QuantityResult:
    value: Decimal
    unit: str
    formula: str
    substituted_formula: str
    citations: Tuple[str, ...]


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuantityCalculationError(f"{label} must be a non-empty string")
    return value.strip()


def _positive_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise QuantityCalculationError(f"{label} must be a number")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise QuantityCalculationError(f"{label} must be a valid number") from exc
    if not number.is_finite():
        raise QuantityCalculationError(f"{label} must be a finite number")
    if number <= 0:
        raise QuantityCalculationError(f"{label} must be greater than zero")
    return number


def _dimension_in_metres(dimension: Dimension, label: str) -> Decimal:
    if not isinstance(dimension, Dimension):
        raise QuantityCalculationError(f"{label} must be a Dimension")
    number = _positive_decimal(dimension.value, label)
    if not isinstance(dimension.unit, str) or not dimension.unit.strip():
        raise QuantityCalculationError(
            f"{label} has no unit; expected mm, cm or m"
        )
    unit = dimension.unit.strip().lower()
    factor = _LENGTH_UNIT_TO_M.get(unit)
    if factor is None:
        raise QuantityCalculationError(
            f"{label} has unknown unit {dimension.unit!r}; expected mm, cm or m"
        )
    _text(dimension.component_code, f"{label}.component_code")
    _text(dimension.citation, f"{label}.citation")
    if dimension.revision is not None:
        _text(dimension.revision, f"{label}.revision")
    return number * factor


def _same_member(dimensions: Tuple[Dimension, ...]) -> None:
    codes = {
        _text(dimension.component_code, "component_code")
        for dimension in dimensions
    }
    if len(codes) != 1:
        raise QuantityCalculationError(
            "dimensions belong to different component codes: "
            + ", ".join(sorted(codes))
        )
    revisions = {
        (dimension.revision or "").strip() for dimension in dimensions
    }
    if len(revisions) != 1:
        shown = ", ".join(sorted(revision or "<missing>" for revision in revisions))
        raise QuantityCalculationError(
            "dimensions belong to different revisions: " + shown
        )


def _format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def rectangular_area(
    length: Dimension, width: Optional[Dimension] = None
) -> QuantityResult:
    """Return ``length × width`` in m² from two sourced dimensions."""

    if width is None:
        raise QuantityCalculationError("missing width for rectangular area")
    dimensions = (length, width)
    length_m = _dimension_in_metres(length, "length")
    width_m = _dimension_in_metres(width, "width")
    _same_member(dimensions)
    value = length_m * width_m
    return QuantityResult(
        value=value,
        unit="m²",
        formula="A = L × W",
        substituted_formula=(
            f"A = {_format_decimal(length_m)} m × "
            f"{_format_decimal(width_m)} m = {_format_decimal(value)} m²"
        ),
        citations=tuple(
            dimension.citation.strip() for dimension in dimensions
        ),
    )


def rectangular_volume(
    length: Dimension,
    width: Optional[Dimension] = None,
    depth: Optional[Dimension] = None,
) -> QuantityResult:
    """Return ``length × width × depth`` in m³ from sourced dimensions."""

    if width is None:
        raise QuantityCalculationError("missing width for rectangular volume")
    if depth is None:
        raise QuantityCalculationError("missing depth for rectangular volume")
    dimensions = (length, width, depth)
    length_m = _dimension_in_metres(length, "length")
    width_m = _dimension_in_metres(width, "width")
    depth_m = _dimension_in_metres(depth, "depth")
    _same_member(dimensions)
    value = length_m * width_m * depth_m
    return QuantityResult(
        value=value,
        unit="m³",
        formula="V = L × W × D",
        substituted_formula=(
            f"V = {_format_decimal(length_m)} m × "
            f"{_format_decimal(width_m)} m × "
            f"{_format_decimal(depth_m)} m = {_format_decimal(value)} m³"
        ),
        citations=tuple(
            dimension.citation.strip() for dimension in dimensions
        ),
    )
