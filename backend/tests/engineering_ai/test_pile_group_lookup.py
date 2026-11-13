import json

from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument
from app.engineering_ai.pile_group_lookup import find_proposed_pile_group


def test_group_rows_preserve_ambiguous_code_and_skip_duplicate_table(session_factory):
    with session_factory() as db:
        document = SourceDocument(id="drawing", project_id="project", type="drawing", original_name="drawing.pdf", document_key="drawing", original_path="/tmp/drawing.pdf", sha256="a" * 64, status="ready")
        page = DocumentPage(id="page", project_id="project", document_id="drawing", page_number=7)
        extraction = PageExtraction(id="extract", project_id="project", document_id="drawing", page_id="page", page_number=7, model="test", prompt_version="1", mode="direct", status="proposed", extraction_json=json.dumps({"title": "MẶT BẰNG NHÓM CỌC NHÓM 1", "table_rows": [
            ["Phân loại", "Phân đoạn", "Vị trí", "Tên cọc (KS)", "Chiều dài vết nứt L (m)"],
            ["Nhóm 1", "Phân đoạn 2", "Cầu chính", "H77", "0,2"],
            ["", "", "", "F66", "0,4"],
            ["", "Phân đoạn 12", "Cầu dẫn", "M297, M299, 299", "0,2"],
            ["Tên cọc (KS)", "Chiều dài vết nứt L (m)"],
            ["H77", "0,2"],
            ["CTTK", "PHẠM THÀNH TRUNG", ""],
            ["THIẾT KẾ", "HOÀNG THẾ NGHĨA", ""],
            ["LẦN", "NGÀY", "NỘI DUNG CẬP NHẬT"],
            ["1", "CMB - TKCT.CNHP", "3"],
        ]}, ensure_ascii=False))
        db.add_all([document, page, extraction]); db.commit()
        result = find_proposed_pile_group(db, "project", 1)
        assert [entry.code for entry in result.entries] == ["H77", "F66", "M297", "M299", "299"]
        assert result.raw_count == 5
        assert result.entries[-1].ambiguous
        assert result.entries[0].table_row == 1
        assert result.entries[0].url.endswith("/documents/drawing/pages/7")
        assert [entry.code for entry in find_proposed_pile_group(db, "project", 1, location="Cầu chính").entries] == ["H77", "F66"]
        assert [entry.code for entry in find_proposed_pile_group(db, "project", 1, segment=12).entries] == ["M297", "M299", "299"]
        assert find_proposed_pile_group(db, "other", 1).entries == ()


def test_non_source_table_and_unanchored_block_do_not_inherit_segment(session_factory):
    with session_factory() as db:
        document = SourceDocument(
            id="drawing", project_id="project", type="drawing",
            original_name="drawing.pdf", document_key="drawing",
            original_path="/tmp/drawing.pdf", sha256="b" * 64, status="ready",
        )
        page = DocumentPage(
            id="page", project_id="project", document_id="drawing", page_number=8
        )
        extraction = PageExtraction(
            id="extract", project_id="project", document_id="drawing",
            page_id="page", page_number=8, model="test", prompt_version="1",
            mode="direct", status="proposed", extraction_json=json.dumps({
                "title": "MẶT BẰNG NHÓM CỌC NHÓM 2 (1/7)",
                "table_rows": [
                    # A table with a different header suffix (CĐ) is not the
                    # repair-plan table and must not contribute codes.
                    ["Phân đoạn", "Tên cọc (CĐ)", "Chiều dài (m)"],
                    ["Phân đoạn 1", "C1", "1.7"],
                    ["Phân đoạn 1", "C3", "0.6"],
                    ["Phân loại", "Phân đoạn", "Tên cọc (KT)",
                     "Chiều dài vết nứt L (m)"],
                    ["", "", "I3", "1,1"],
                    ["", "", "I4", "0,5"],
                    # Merged segment cell is read at the end of the block.
                    ["Nhóm 2", "Phân đoạn 1", "", ""],
                    # Layout changes; these rows cannot be anchored to the
                    # preceding segment and must not be assigned segment 1.
                    ["NHÃN", "GIÁ TRỊ"],
                    ["E148", "0,9"],
                    ["C146", "0,9"],
                ],
            }, ensure_ascii=False),
        )
        db.add_all([document, page, extraction])
        db.commit()

        result = find_proposed_pile_group(db, "project", 2)

        assert [entry.code for entry in result.entries] == ["I3", "I4"]
        assert {entry.segment for entry in result.entries} == {"1"}
        assert {entry.group for entry in result.entries} == {"2"}
        assert not {"C1", "C3", "E148", "C146"} & {
            entry.code for entry in result.entries
        }
        assert any("bỏ qua 2 dòng" in warning for warning in result.warnings)


def test_duplicate_readings_reconcile_against_statistics_register(session_factory):
    with session_factory() as db:
        document = SourceDocument(
            id="drawing", project_id="project", type="drawing",
            original_name="drawing.pdf", document_key="drawing",
            original_path="/tmp/drawing.pdf", sha256="c" * 64, status="ready",
        )
        page9 = DocumentPage(
            id="page9", project_id="project", document_id="drawing", page_number=9
        )
        page25 = DocumentPage(
            id="page25", project_id="project", document_id="drawing", page_number=25
        )
        header = ["Phân loại", "Phân đoạn", "Tên cọc (KS)", "Chiều dài (m)"]
        db.add_all([
            document,
            page9,
            page25,
            PageExtraction(
                id="extract9", project_id="project", document_id="drawing",
                page_id="page9", page_number=9, model="test", prompt_version="1",
                mode="direct", status="proposed", extraction_json=json.dumps({
                    "title": "MẶT BẰNG NHÓM CỌC NHÓM 2 (2/7)",
                    "summary": "Bố trí nhóm cọc 2, phân đoạn 3 - cầu chính.",
                    "table_rows": [
                        header,
                        ["Nhóm 2", "Phân đoạn 3", "I111", "1,2"],
                        ["", "", "I113", "0,7"],
                        ["", "", "I135", "0,8"],
                        ["", "", "H134", "1"],
                        ["", "", "G122", "1"],
                        ["", "", "F108", "0,6"],
                        ["", "", "B184", "1,6"],
                        header,
                        ["Nhóm 2", "Phân đoạn 3", "I111", "1,2"],
                        ["", "", "I133", "0,7"],
                        ["", "", "I136", "0,8"],
                        ["", "", "G98", "1,2"],
                        ["", "", "F106", "0,6"],
                        ["", "", "B164", "1,6"],
                    ],
                }, ensure_ascii=False),
            ),
            PageExtraction(
                id="extract25", project_id="project", document_id="drawing",
                page_id="page25", page_number=25, model="test",
                prompt_version="1", mode="direct", status="proposed",
                extraction_json=json.dumps({
                    "title": "BẢNG THỐNG KÊ CỌC HƯ HỎNG NHÓM II",
                    "table_rows": [
                        ["Nhóm", "Vị trí", "Tên cọc", "Số cọc"],
                        ["II.1", "Cầu chính",
                         "I133, I136, H134, G122, G98, F108, F106, B164", "8"],
                    ],
                }, ensure_ascii=False),
            ),
        ])
        db.commit()

        result = find_proposed_pile_group(db, "project", 2, location="Cầu chính")

        codes = [entry.code for entry in result.entries]
        assert codes.count("I111") == 1
        assert {"I133", "I136", "H134", "G122", "G98", "F108", "B164"} <= set(codes)
        assert not {"I113", "I135", "B184"} & set(codes)
        assert any(
            "F108" in warning and "F106" in warning
            for warning in result.warnings
        )
