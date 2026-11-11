"""Focused tests for the zip-preserving worksheet XML writer."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.acceptance.errors import TemplateError
from app.acceptance.template import (
    DEFAULT_TEMPLATE_PATH,
    set_cell_xml,
    template_path,
    validate_template,
)


def test_set_cell_preserves_style_and_formula_replacement():
    xml = (
        '<worksheet><sheetData><row r="6">'
        '<c r="B6" s="127"><v>32</v></c>'
        '<c r="C6" s="128"/>'
        '</row></sheetData></worksheet>'
    )
    updated = set_cell_xml(xml, "B6", "validated")
    assert 's="127"' in updated
    assert "t=\"inlineStr\"" in updated
    assert "validated" in updated
    assert "<f>" not in updated


def test_set_cell_clears_value_but_keeps_style():
    xml = '<worksheet><sheetData><row r="20"><c r="A20" s="148" t="s"><v>7</v></c></row></sheetData></worksheet>'
    updated = set_cell_xml(xml, "A20", None)
    assert '<c r="A20" s="148"/>' in updated
    assert "<v>7</v>" not in updated


def test_set_cell_inserts_missing_cell_with_neighbour_style():
    xml = (
        '<worksheet><sheetData><row r="10">'
        '<c r="A10" s="1"/><c r="C10" s="3"/>'
        '</row></sheetData></worksheet>'
    )
    updated = set_cell_xml(xml, "B10", "new")
    assert '<c r="B10" s="1"' in updated or '<c r="B10" s="3"' in updated
    assert updated.index('r="A10"') < updated.index('r="B10"') < updated.index('r="C10"')


def test_inserts_missing_row_in_sorted_position():
    xml = (
        '<worksheet><sheetData><row r="1"><c r="A1" s="1"/></row>'
        '<row r="3"><c r="A3" s="1"/></row></sheetData></worksheet>'
    )
    updated = set_cell_xml(xml, "B2", "new")
    assert updated.index('r="1"') < updated.index('r="2"') < updated.index('r="3"')


def test_validate_rejects_missing_template(tmp_path):
    with pytest.raises(TemplateError) as exc:
        validate_template(tmp_path / "missing.xlsx")
    assert exc.value.code == "template_missing"


def test_validate_accepts_canonical_template_if_present():
    # Repo-owned canonical copy, never the user's working file in Downloads.
    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "templates"
        / "acceptance-original.xlsx"
    )
    if not path.is_file():
        pytest.skip("canonical acceptance template not present")
    assert validate_template(path) == path


def test_default_template_path_is_repo_canonical_and_cwd_independent(monkeypatch, tmp_path):
    monkeypatch.delenv("ACCEPTANCE_TEMPLATE", raising=False)
    monkeypatch.chdir(tmp_path)

    assert DEFAULT_TEMPLATE_PATH == (
        Path(__file__).resolve().parents[3]
        / "data"
        / "templates"
        / "acceptance-original.xlsx"
    )
    assert "Downloads" not in str(DEFAULT_TEMPLATE_PATH)
    assert template_path() == DEFAULT_TEMPLATE_PATH


def test_missing_canonical_default_reports_clear_error(monkeypatch, tmp_path):
    monkeypatch.delenv("ACCEPTANCE_TEMPLATE", raising=False)
    missing = tmp_path / "absent-canonical.xlsx"
    monkeypatch.setattr("app.acceptance.template.DEFAULT_TEMPLATE_PATH", missing)

    with pytest.raises(TemplateError) as exc:
        validate_template()
    assert exc.value.code == "template_missing"
    assert str(missing) in str(exc.value)
    assert "Downloads" not in str(exc.value)
