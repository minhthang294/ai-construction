from decimal import Decimal

import pytest

from app.engineering_ai.quantity_calc import (
    Dimension,
    QuantityCalculationError,
    rectangular_area,
    rectangular_volume,
)


def _dimension(value, unit, code, citation, revision="A"):
    return Dimension(
        value=value,
        unit=unit,
        component_code=code,
        citation=citation,
        revision=revision,
    )


def test_rectangular_area_converts_mm_to_m2():
    length = _dimension(1500, "mm", "P-01", "synthetic page 1, length cell")
    width = _dimension(200, "mm", "P-01", "synthetic page 1, width cell")

    result = rectangular_area(length, width)

    assert result.value == Decimal("0.3")
    assert result.unit == "m²"
    assert result.formula == "A = L × W"
    assert result.substituted_formula == "A = 1.5 m × 0.2 m = 0.3 m²"
    assert result.citations == (
        "synthetic page 1, length cell",
        "synthetic page 1, width cell",
    )


def test_rectangular_volume_converts_mm_and_cm_to_m3():
    length = _dimension(1500, "mm", "P-01", "synthetic page 1, length cell")
    width = _dimension(200, "mm", "P-01", "synthetic page 1, width cell")
    depth = _dimension(1, "cm", "P-01", "synthetic page 1, depth cell")

    result = rectangular_volume(length, width, depth)

    assert result.value == Decimal("0.003")
    assert result.unit == "m³"
    assert result.formula == "V = L × W × D"
    assert result.substituted_formula == (
        "V = 1.5 m × 0.2 m × 0.01 m = 0.003 m³"
    )
    assert result.citations == (
        "synthetic page 1, length cell",
        "synthetic page 1, width cell",
        "synthetic page 1, depth cell",
    )


def test_rectangular_area_requires_width():
    length = _dimension(1500, "mm", "P-01", "synthetic page 1, length cell")

    with pytest.raises(QuantityCalculationError, match="missing width"):
        rectangular_area(length)


def test_rectangular_quantity_rejects_mixed_components_or_revisions():
    length = _dimension(1500, "mm", "P-01", "synthetic page 1, length cell")
    other_component = _dimension(
        200, "mm", "P-02", "synthetic page 2, width cell"
    )
    with pytest.raises(QuantityCalculationError, match="different component codes"):
        rectangular_area(length, other_component)

    width = _dimension(200, "mm", "P-01", "synthetic page 1, width cell")
    depth_revision_b = _dimension(
        1, "cm", "P-01", "synthetic page 2, depth cell", revision="B"
    )
    with pytest.raises(QuantityCalculationError, match="different revisions"):
        rectangular_volume(length, width, depth_revision_b)


def test_rectangular_area_rejects_unknown_unit_and_non_positive_values():
    width = _dimension(200, "mm", "P-01", "synthetic page 1, width cell")
    unknown = _dimension(1500, "ft", "P-01", "synthetic page 1, length cell")
    with pytest.raises(QuantityCalculationError, match="unknown unit"):
        rectangular_area(unknown, width)

    zero = _dimension(0, "mm", "P-01", "synthetic page 1, length cell")
    with pytest.raises(QuantityCalculationError, match="greater than zero"):
        rectangular_area(zero, width)

    negative = _dimension(-1, "mm", "P-01", "synthetic page 1, length cell")
    with pytest.raises(QuantityCalculationError, match="greater than zero"):
        rectangular_area(negative, width)
