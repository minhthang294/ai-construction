import json

from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument
from app.engineering_ai.pile_table_lookup import _measurement, find_proposed_pile_measurements


def test_generic_length_column_needs_pile_plan_title():
    assert _measurement("chieu dai (m)", "mat bang nhom coc nhom 2") == ("chiều dài vết nứt L", "m")
    assert _measurement("chieu dai (m)", "bang khoi luong") is None


def test_exact_pile_rows_and_explicit_measurements(session_factory):
    with session_factory() as db:
        document = SourceDocument(id="d1", project_id="p1", original_name="drawing.pdf",
                                  document_key="drawing", original_path="/tmp/drawing.pdf",
                                  sha256="a" * 64, status="ready", is_effective=True)
        page = DocumentPage(id="pg1", project_id="p1", document_id="d1", page_number=25)
        table = [
            ["Nhóm", "Vị trí", "Tên cọc", "L1 (m)", "L2 (m)", "t (cm)"],
            ["II.1", "Cầu chính", "F27", "0,5", "", "1"],
            ["", "", "F270", "0,8", "0,2", "3"],
            ["", "", "F27, E152", "0,6", "0,1", "2"],
            ["STT", "Hạng mục", "Đơn vị", "Khối lượng"],
            ["1", "F27", "m3", "999"],
            ["Tên cọc (KS)", "Chiều dài vết nứt L (m)"],
            ["F27", "1,2"],
            ["F27", "n/a"],
        ]
        extraction = PageExtraction(id="e1", project_id="p1", document_id="d1", page_id="pg1",
                                    page_number=25, model="test", prompt_version="1", mode="direct",
                                    status="proposed", extraction_json=json.dumps({"table_rows": table}))
        db.add_all([document, page, extraction])
        db.commit()
        matches = find_proposed_pile_measurements(db, "p1", "F27")
        assert [(m.table_row, m.table_column, m.fact["value"]) for m in matches] == [
            (2, "l1 (m)", "0,5"), (2, "t (cm)", "1"),
            (4, "l1 (m)", "0,6"), (4, "l2 (m)", "0,1"),
            (4, "t (cm)", "2"), (8, "chieu dai vet nut l (m)", "1,2"),
        ]
        assert matches[0].fact["location"] == "Cầu chính"
        assert matches[-1].fact["location"] == ""
        assert all(m.fact["status"] == "proposed" for m in matches)
        assert find_proposed_pile_measurements(db, "p2", "F27") == []
        assert find_proposed_pile_measurements(db, "p1", "F2") == []
