import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.engineering_ai.dap_design import (
    build_candidate_report,
    build_from_review_database,
    facts_to_work_items,
    load_review_database,
    stage_review_database,
)

SOURCES = {
    "h1": {"name": "drawing.pdf", "kind": "DRAWING"},
    "h2": {"name": "thkl.xlsx", "kind": "THKL"},
}


def component(**overrides):
    row = {
        "source_hash": "h1",
        "zone": "Cầu chính",
        "segment": 2,
        "kind": "PILE",
        "design_group": 1,
        "raw_code": "H77",
        "page": 7,
        "drawing": "TK-01",
        "review_status": "NEEDS_REVIEW",
        "note": "",
    }
    row.update(overrides)
    return row


def thkl_row(row_number, cells, sheet="01_COC_PD1"):
    return {
        "source_hash": "h2",
        "sheet": sheet,
        "row_number": row_number,
        "zone": "Cầu chính",
        "segment": 1,
        "entry_kind": "DESIGN_SOURCE",
        "review_status": "NEEDS_REVIEW",
        "cells_json": json.dumps(cells),
    }


def report(**overrides):
    values = {
        "components": [],
        "sources": SOURCES,
        "notes": [],
        "thkl_rows": [],
        "project_id": "dap",
    }
    values.update(overrides)
    return build_candidate_report(**values)


def test_component_candidate_needs_source_page_and_exact_code():
    result = report(
        components=[
            component(),
            component(raw_code="I3", page=None),
            component(raw_code="A-1"),
            component(source_hash="missing"),
        ]
    )

    assert [c.raw_code for c in result.components] == ["H77"]
    candidate = result.components[0]
    assert candidate.project_id == "dap"
    assert candidate.stage is None
    assert candidate.revision is None
    assert candidate.source.source_hash == "h1"
    assert candidate.source.page == 7
    assert candidate.source.drawing == "TK-01"
    assert any("page" in issue for issue in result.conflicts)
    assert any("code" in issue for issue in result.conflicts)
    assert any("source" in issue for issue in result.conflicts)


def test_same_code_in_two_groups_is_a_conflict_not_two_candidates():
    result = report(
        components=[
            component(design_group=2),
            component(design_group=3, page=15, drawing="TK-09"),
        ]
    )

    assert len(result.components) == 1
    assert result.components[0].design_group == 2
    assert any("group" in issue for issue in result.conflicts)


def test_reviewed_candidate_is_refused_by_the_candidate_pipeline():
    result = report(components=[component(review_status="VERIFIED")])

    assert result.components == ()
    assert any("NEEDS_REVIEW" in issue for issue in result.conflicts)


def test_design_work_matrix_keeps_value_provenance_and_skips_formulas():
    rows = [
        thkl_row(5, ["STT", "Hạng mục công việc", "Đơn vị", "I3", "I4"]),
        thkl_row(8, ["1", "Chiều dài xử lý theo thiết kế", "m", "1.1", 0.5]),
        thkl_row(9, ["2", "Chiều sâu đục t theo thiết kế", "cm", 3, None]),
        thkl_row(10, ["3", "Đục bê tông om vỡ theo t", "m³", "=A1*2", None]),
    ]

    result = report(thkl_rows=rows)

    assert len(result.work_items) == 3
    first = result.work_items[0]
    assert (first.code, first.work_name, first.unit, first.value) == (
        "I3",
        "Chiều dài xử lý theo thiết kế",
        "m",
        1.1,
    )
    assert first.kind == "PILE"
    assert first.source.sheet == "01_COC_PD1"
    assert first.source.row == 8
    assert first.source.column == 4
    assert first.project_id == "dap"
    assert first.stage is None
    assert all("=" not in str(item.raw_value) for item in result.work_items)


def test_beam_sheet_keeps_beam_codes_and_skips_total_column():
    rows = [
        thkl_row(5, ["STT", "Hạng mục", "Đơn vị", "F-1-11", "TỔNG DẦM"], sheet="02_DAM_PD1"),
        thkl_row(8, ["1", "Cốt thép bổ sung", "Kg", 54.75, 99.0], sheet="02_DAM_PD1"),
    ]

    result = report(thkl_rows=rows)

    assert len(result.work_items) == 1
    item = result.work_items[0]
    assert (item.code, item.kind, item.value) == ("F-1-11", "BEAM", 54.75)


def test_project_is_required_and_unknown_stage_stays_null():
    with pytest.raises(ValueError):
        report(project_id="")
    result = report(revision="REV1")
    assert result.stage is None
    assert result.revision == "REV1"


REVIEW_DB = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "storage"
    / "design-review"
    / "dap-design.sqlite3"
)


@pytest.mark.skipif(not REVIEW_DB.exists(), reason="local review database not available")
def test_review_database_builds_pd2_candidates_without_writing():
    before = hashlib.sha256(REVIEW_DB.read_bytes()).hexdigest()

    dataset = load_review_database(REVIEW_DB)
    assert len(dataset["components"]) == 75
    assert len(dataset["notes"]) == 3
    assert len(dataset["thkl_rows"]) == 365

    result = build_from_review_database(REVIEW_DB, project_id="dap")

    assert hashlib.sha256(REVIEW_DB.read_bytes()).hexdigest() == before
    assert result.stage is None and result.revision is None
    assert len(result.components) == 75
    assert {c.zone for c in result.components} == {"Cầu chính"}
    assert {c.segment for c in result.components} == {2}
    assert {c.kind for c in result.components} == {"PILE"}
    counts = {}
    for candidate in result.components:
        counts[candidate.design_group] = counts.get(candidate.design_group, 0) + 1
    assert counts == {1: 3, 2: 33, 3: 39}
    assert all(c.review_status == "NEEDS_REVIEW" for c in result.components)
    assert all(c.source.page and c.source.drawing and c.source.source_hash for c in result.components)
    assert result.pages_needing_review == (6, 7, 8, 15)
    assert any("F5" in note.note or "I49" in note.note for note in result.notes)

    assert result.work_items
    assert {item.source.sheet.split("_")[0] for item in result.work_items} == {"01", "02"}
    assert all(item.source.row and item.source.column for item in result.work_items)
    assert all(item.value is not None for item in result.work_items)
    assert all(item.stage is None for item in result.work_items)


GOLDEN_PAGE = {
    "page_number": 22,
    "document_name": "drawing.pdf",
    "extraction": {
        "drawing_number": "TK-16",
        "revision": None,
        "component_facts": [
            {
                "component_type": "pile",
                "component_code": "H77",
                "fact_name": "chiều sâu đục",
                "value": "1",
                "unit": "cm",
                "group": "1",
                "segment": "2",
                "location": "Cầu chính",
                "source_page": 22,
                "source_row": 1,
                "source_column": "t (cm)",
                "source_sheet": "TK-16",
                "evidence_kind": "joined",
            },
            {
                "component_type": "pile",
                "component_code": "H77",
                "fact_name": "phân loại",
                "value": "Loại 1",
                "unit": "loại",
                "group": "1",
                "segment": "2",
                "location": "Cầu chính",
                "source_page": 22,
                "source_row": 1,
                "source_column": "Loại",
                "source_sheet": "TK-16",
                "evidence_kind": "direct",
            },
            {
                "component_type": "pile",
                "component_code": "H77",
                "fact_name": "thiếu cột",
                "value": "2",
                "unit": "m3",
                "group": "1",
                "segment": "2",
                "location": "Cầu chính",
                "source_page": 22,
                "source_row": 1,
                "source_column": None,
                "source_sheet": "TK-16",
                "evidence_kind": "joined",
            },
        ],
    },
}


def test_joined_fact_keeps_provenance_and_needs_source_cell():
    items = facts_to_work_items(GOLDEN_PAGE, sources=SOURCES, project_id="dap")

    assert len(items) == 1
    item = items[0]
    assert (item.kind, item.code, item.work_name, item.unit, item.value) == (
        "PILE",
        "H77",
        "chiều sâu đục",
        "cm",
        1.0,
    )
    assert item.source.page == 22 and item.source.sheet == "TK-16"
    assert item.source.row == 1 and item.source.column == "t (cm)"
    assert item.evidence_kind == "joined"
    assert item.stage is None and item.revision is None

    revised = json.loads(json.dumps(GOLDEN_PAGE))
    revised["extraction"]["revision"] = "REV1"
    assert facts_to_work_items(revised, sources=SOURCES, project_id="dap")[0].revision == "REV1"


def test_staging_writes_only_to_sandbox_and_is_idempotent(tmp_path):
    if not REVIEW_DB.exists():
        pytest.skip("local review database not available")
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "component_qa_golden_2026-11-12"
        / "page_022.json"
    )
    if not fixture.exists():
        pytest.skip("golden page fixture not available")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    original = REVIEW_DB.read_bytes()
    before = hashlib.sha256(original).hexdigest()

    sandbox = tmp_path / "design-review"
    sandbox.mkdir()
    db = sandbox / "dap-copy.sqlite3"
    db.write_bytes(original)
    with sqlite3.connect(db) as connection:
        connection.execute("drop table if exists design_work_items")

    first = stage_review_database(db, project_id="dap", fixtures=[payload])
    assert first.inserted == len(first.items) == 1344
    assert first.conflicts == ()
    assert {item.kind for item in first.items if item.source.page == 22} == {"PILE"}
    assert all(item.stage is None for item in first.items)

    with sqlite3.connect(db) as connection:
        assert connection.execute("select count(*) from component_candidates").fetchone()[0] == 75
        assert connection.execute(
            "select count(*) from design_work_items where stage is not null"
        ).fetchone()[0] == 0

    second = stage_review_database(db, project_id="dap", fixtures=[payload])
    assert second.inserted == 0
    assert second.existing == 1344
    assert hashlib.sha256(REVIEW_DB.read_bytes()).hexdigest() == before

    with pytest.raises(ValueError):
        stage_review_database(Path("data/app.db"), project_id="dap")
