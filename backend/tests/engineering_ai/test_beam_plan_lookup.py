import json

from app.engineering_ai.beam_plan_lookup import find_proposed_beam_plan
from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument


def test_beam_plan_exact_location_and_malformed_rows(session_factory):
    with session_factory() as db:
        doc = SourceDocument(id="plan", project_id="p1", type="drawing", original_name="plan.pdf",
                             document_key="plan", original_path="/tmp/plan.pdf", sha256="a" * 64,
                             status="ready", is_effective=True, page_count=1)
        page = DocumentPage(id="plan-page", project_id="p1", document_id=doc.id, page_number=103)
        extraction = PageExtraction(
            id="plan-extraction", project_id="p1", document_id=doc.id, page_id=page.id,
            page_number=103, model="test", prompt_version="test", mode="direct", status="proposed",
            extraction_json=json.dumps({"title": "MẶT BẰNG, KÝ HIỆU VÀ PHÂN NHÓM SỬA CHỮA - CẦU DẪN",
                                        "table_rows": [
                                            ["Phân nhóm", "Phân đoạn", "Ký hiệu dầm", "Loại dầm"],
                                            ["1", "PĐ12", "Q-295", "Dầm ngang"],
                                            ["PĐ12", "", "Q-295", ""],
                                            ["2", "PĐ13", "Q-299", "Dầm dọc"],
                                        ]}),
        )
        db.add_all([doc, page, extraction])
        db.commit()
        found = find_proposed_beam_plan(db, "p1", "Q-295")
        assert len(found) == 1
        assert (found[0].group, found[0].segment, found[0].location, found[0].beam_type) == (
            "1", "PD12", "Cầu dẫn", "Dầm ngang"
        )
        assert (found[0].page_number, found[0].table_row) == (103, 2)
        assert find_proposed_beam_plan(db, "p1", "Q-296") == []
        assert find_proposed_beam_plan(db, "p2", "Q-295") == []
