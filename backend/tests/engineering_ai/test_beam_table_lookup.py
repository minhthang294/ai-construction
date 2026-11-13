import json

from app.engineering_ai.beam_table_lookup import find_proposed_beam_table_facts
from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument


def _add(db, suffix, code, *, status="proposed", effective=True, project="p1"):
    doc = SourceDocument(id=f"doc-{suffix}", project_id=project, type="drawing",
                         original_name=f"{suffix}.pdf", document_key=suffix,
                         original_path=f"/tmp/{suffix}.pdf", sha256=suffix * 64,
                         status="ready", is_effective=effective, page_count=1)
    page = DocumentPage(id=f"page-{suffix}", project_id=project,
                        document_id=doc.id, page_number=93)
    extraction = PageExtraction(
        id=f"ext-{suffix}", project_id=project, document_id=doc.id,
        page_id=page.id, page_number=93, model="test", prompt_version="test",
        mode="direct", status=status,
        extraction_json=json.dumps({"table_rows": [
            ["STT", "Tên dầm", "L(mm)", "B(mm)", "Khối lượng trám vá đáy 3cm (m3)"],
            ["1", code, "1900", "700", "0.330"],
            ["2", "F-10-11", "2000", "700", "0.450"],
            ["3", "F-12", "1..2", "700", "-"],
        ]}),
    )
    db.add_all([doc, page, extraction])


def test_exact_beam_row_numeric_cells_and_source(session_factory):
    with session_factory() as db:
        _add(db, "a", "G-F.89")
        _add(db, "b", "G-F.89", effective=False)
        _add(db, "c", "G-F.89", project="p2")
        _add(db, "d", "G-F.89", status="rejected")
        db.commit()
        found = find_proposed_beam_table_facts(db, "p1", "g-f.89")
        assert {(m.fact["fact_name"], m.fact["value"]) for m in found} == {
            ("chiều dài dầm", "1900"), ("chiều rộng dầm", "700"),
            ("khối lượng tram va day 3cm", "0.330"),
        }
        assert all(m.table_row == 2 and m.page_number == 93 and m.document_id == "doc-a" for m in found)
        assert all(m.fact["status"] == "proposed" and m.table_column for m in found)
        assert len(find_proposed_beam_table_facts(db, "p1", "G-F.89", "history")) == 6
        assert find_proposed_beam_table_facts(db, "p1", "F-10") == []
        assert find_proposed_beam_table_facts(db, "p1", "F-12") == [m for m in find_proposed_beam_table_facts(db, "p1", "F-12") if m.fact["fact_name"] == "chiều rộng dầm"]
