import json

from app.engineering_ai.component_chat import _dimension_value
from app.engineering_ai.constants import NO_SOURCE_ANSWER, UNVERIFIED_KB_NOTE
from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument


def _document(
    db,
    project_id="p1",
    suffix="a",
    *,
    effective=True,
    revision="A",
    page_numbers=(1,),
):
    document = SourceDocument(
        id=f"doc-{suffix}",
        project_id=project_id,
        type="drawing",
        original_name=f"drawing-{suffix}.pdf",
        document_key=f"drawing-{suffix}",
        original_path=f"/tmp/drawing-{suffix}.pdf",
        sha256=(suffix * 64)[:64],
        status="ready",
        is_current=True,
        is_effective=effective,
        page_count=len(page_numbers),
        revision=revision,
        drawing_number="TK-02",
    )
    pages = [
        DocumentPage(
            id=f"page-{suffix}-{number}",
            project_id=project_id,
            document_id=document.id,
            page_number=number,
            revision=revision,
            drawing_number="TK-02",
        )
        for number in page_numbers
    ]
    db.add_all([document, *pages])
    return document, pages


def _extraction(
    db,
    document,
    page,
    suffix,
    facts,
    *,
    status="verified",
    drawing_number=None,
    revision=None,
):
    payload = {"component_facts": facts}
    if drawing_number is not None:
        payload["drawing_number"] = drawing_number
    if revision is not None:
        payload["revision"] = revision
    db.add(
        PageExtraction(
            id=f"ext-{suffix}-{page.page_number}",
            project_id=document.project_id,
            document_id=document.id,
            page_id=page.id,
            page_number=page.page_number,
            model="test",
            prompt_version=suffix,
            mode="direct",
            status=status,
            extraction_json=json.dumps(payload, ensure_ascii=False),
        )
    )


def _fact(
    code,
    name,
    value,
    unit,
    *,
    quote=None,
    group="Nhóm 1",
    segment="Phân đoạn 2",
    location="Cầu chính",
    component_type="pile",
    table_row=1,
):
    return {
        "component_type": component_type,
        "component_code": code,
        "fact_name": name,
        "value": value,
        "unit": unit,
        "quote": quote or f"{name} = {value} {unit}",
        "group": group,
        "segment": segment,
        "location": location,
        "table_row": table_row,
        "table_column": name,
    }


def _chat(client, message):
    response = client.post(
        "/api/v1/projects/p1/ai/chat", json={"message": message}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_exact_pile_code_uses_verified_effective_fact(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="h77", page_numbers=(22,))
        _extraction(
            db,
            document,
            pages[0],
            "h77",
            [
                _fact(
                    "H77",
                    "chiều sâu đục",
                    "1",
                    "cm",
                    quote="t = 1 cm",
                    group="Nhóm 1",
                    segment="Phân đoạn 2",
                )
            ],
        )
        document_id = document.id
        db.commit()

    body = _chat(client, "Cọc H77 đục sâu bao nhiêu?")

    assert body["no_source"] is False
    assert body["confidence"] > 0
    assert "H77" in body["answer"]
    assert "chiều sâu đục: 1 cm" in body["answer"]
    assert "hồ sơ ghi sẵn (trực tiếp)" in body["answer"]
    assert UNVERIFIED_KB_NOTE not in body["warnings"]
    assert answer_provider.calls == []
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["document_id"] == document_id
    assert citation["page_number"] == 22
    assert citation["revision"] == "A"
    assert citation["quote"] == "t = 1 cm"
    assert citation["url"].endswith(f"/documents/{document_id}/pages/22")


def test_joined_quantity_is_labeled_as_cross_table_evidence(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="joined", page_numbers=(22,))
        fact = _fact("H77", "thể tích đục", "0,003", "m³")
        fact["evidence_kind"] = "joined"
        _extraction(db, document, pages[0], "joined", [fact])
        db.commit()
    body = _chat(client, "Cọc H77 thể tích đục bao nhiêu?")
    assert "đối chiếu các bảng trong hồ sơ" in body["answer"]
    assert "hồ sơ ghi sẵn (trực tiếp)" not in body["answer"]


def test_chipping_quantity_uses_sourced_volume(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="chip", page_numbers=(22,))
        _extraction(db, document, pages[0], "chip", [
            _fact("H77", "thể tích đục", "0,003", "m³")
        ])
        db.commit()
    body = _chat(client, "Cọc H77 khối lượng đục bao nhiêu?")
    assert "thể tích đục: 0,003 m³" in body["answer"]
    assert "Chưa đủ dữ kiện" not in body["answer"]


def test_specific_depth_does_not_dump_unrelated_facts(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="depth", page_numbers=(22,))
        _extraction(db, document, pages[0], "depth", [
            _fact("H77", "chiều sâu đục", "1", "cm"),
            _fact("H77", "diện tích quét keo", "0,304", "m²"),
        ])
        db.commit()
    body = _chat(client, "Cọc H77 đục sâu bao nhiêu?")
    assert "chiều sâu đục: 1 cm" in body["answer"]
    assert "diện tích quét keo" not in body["answer"]


def test_proposed_exact_pile_depth_is_labeled_and_cited(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="f27", page_numbers=(25,))
        db.add(PageExtraction(
            id="ext-f27-25", project_id="p1", document_id=document.id,
            page_id=pages[0].id, page_number=25, model="test",
            prompt_version="f27", mode="direct", status="proposed",
            extraction_json=json.dumps({"table_rows": [
                ["Nhóm", "Vị trí", "Tên cọc", "Số cọc", "t (cm)"],
                ["II.1", "Cầu chính", "F27", "1", "1"],
                ["II.1", "Cầu chính", "F39, E152", "2", "2"],
            ]}, ensure_ascii=False),
        ))
        db.commit()
    body = _chat(client, "Cọc F27 đục sâu bao nhiêu cm?")
    assert body["no_source"] is False
    assert "F27" in body["answer"] and "1 cm" in body["answer"]
    assert "chưa được kỹ sư xác minh" in body["answer"]
    assert body["citations"][0]["page_number"] == 25
    assert "F27 | t (cm) = 1 cm" in body["citations"][0]["quote"]
    other = _chat(client, "Cọc F2 đục sâu bao nhiêu cm?")
    assert other["no_source"] is True


def test_proposed_measurement_respects_group_and_requested_field(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="f27-group", page_numbers=(25,))
        db.add(PageExtraction(
            id="ext-f27-group", project_id="p1", document_id=document.id,
            page_id=pages[0].id, page_number=25, model="test",
            prompt_version="group", mode="direct", status="proposed",
            extraction_json=json.dumps({"table_rows": [
                ["Nhóm", "Tên cọc", "t (cm)", "Chiều dài vết nứt L (m)"],
                ["Nhóm 2", "F27", "1", "0,8"],
            ]}, ensure_ascii=False),
        ))
        db.commit()
    depth = _chat(client, "Cọc F27 nhóm 2 đục sâu bao nhiêu?")
    assert "1 cm" in depth["answer"]
    assert "0,8 m" not in depth["answer"]
    wrong_group = _chat(client, "Cọc F27 nhóm 1 đục sâu bao nhiêu?")
    assert wrong_group["no_source"] is True
    area = _chat(client, "diện tích quét keo cọc F27 bao nhiêu?")
    assert area["no_source"] is True
    assert "0,8 m" not in area["answer"]
    assert "1 cm" not in area["answer"]


def test_proposed_pile_crack_length_and_beam_quantity_use_exact_rows(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="tables", page_numbers=(7, 93))
        for page, rows in zip(pages, (
            [["Tên cọc (KS)", "Chiều dài vết nứt L (m)"], ["F27", "0,8"], ["F2", "1,1"]],
            [["Tên dầm", "Khối lượng trám vá đáy 3cm (m3)"], ["G-F.89", "0,330"]],
        )):
            db.add(PageExtraction(
                id=f"ext-table-{page.page_number}", project_id="p1", document_id=document.id,
                page_id=page.id, page_number=page.page_number, model="test",
                prompt_version="tables", mode="direct", status="proposed",
                extraction_json=json.dumps({"table_rows": rows}, ensure_ascii=False),
            ))
        db.commit()
    pile = _chat(client, "Cọc F27 chiều dài vết nứt bao nhiêu?")
    assert "0,8 m" in pile["answer"] and pile["citations"][0]["page_number"] == 7
    assert "chưa được kỹ sư xác minh" in pile["answer"]
    beam = _chat(client, "Dầm G-F.89 khối lượng trám vá bao nhiêu?")
    assert "0,330 m³" in beam["answer"] and beam["citations"][0]["page_number"] == 93


def test_pile_group_count_and_list_from_plan_with_ambiguous_code(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="group-plan", page_numbers=(7,))
        db.add(PageExtraction(
            id="ext-group-plan", project_id="p1", document_id=document.id,
            page_id=pages[0].id, page_number=7, model="test",
            prompt_version="group-plan", mode="direct", status="proposed",
            extraction_json=json.dumps({
                "title": "MẶT BẰNG NHÓM CỌC NHÓM 1",
                "table_rows": [
                    ["Phân loại", "Phân đoạn", "Vị trí", "Tên cọc (KS)", "Chiều dài vết nứt L (m)"],
                    ["Nhóm 1", "Phân đoạn 2", "Cầu chính", "H77", "0,2"],
                    ["", "", "", "F66", "0,4"],
                    ["", "Phân đoạn 12", "Cầu dẫn", "M297, 299", "0,3"],
                    ["CTTK", "PHẠM THÀNH TRUNG", "", "", ""],
                    ["KCS", "NGUYỄN VĂN TÙNG", "", "", ""],
                ],
            }, ensure_ascii=False),
        ))
        db.commit()
    count = _chat(client, "có bao nhiêu cọc nhóm 1")
    assert "3 mã cọc rõ ràng" in count["answer"]
    assert "chưa phải tổng số cọc chính thức" in count["answer"]
    assert "Cầu chính" in count["answer"] and "Cầu dẫn" in count["answer"]
    assert "mã cọc không rõ '299'" in count["answer"]
    assert "PHẠM THÀNH TRUNG" not in count["answer"]
    assert count["citations"][0]["page_number"] == 7
    listed = _chat(client, "cọc nhóm một có những cọc nào")
    assert "H77, F66" in listed["answer"]
    assert "M297, 299" not in listed["answer"]


def test_exact_group_question_keeps_statuses_separate_and_reconciles_duplicate_reads(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(
            db, suffix="exact-group", page_numbers=(8, 9, 25)
        )
        _extraction(
            db,
            document,
            pages[0],
            "exact-verified",
            [
                _fact("I3", "tình trạng", "hư hỏng", "", group="Nhóm 2",
                      segment="Phân đoạn 1"),
                _fact("I4", "tình trạng", "hư hỏng", "", group="Nhóm 2",
                      segment="Phân đoạn 1"),
                _fact("H2", "tình trạng", "hư hỏng", "", group="Nhóm 2",
                      segment="Phân đoạn 1"),
            ],
        )
        header = ["Phân loại", "Phân đoạn", "Tên cọc (KS)", "Chiều dài (m)"]
        db.add_all([
            PageExtraction(
                id="ext-exact-p8", project_id="p1", document_id=document.id,
                page_id=pages[0].id, page_number=8, model="test",
                prompt_version="p8", mode="direct", status="proposed",
                extraction_json=json.dumps({
                    "title": "MẶT BẰNG NHÓM CỌC NHÓM 2 (1/7)",
                    "drawing_number": "TK-02",
                    "table_rows": [
                        ["Phân đoạn", "Tên cọc (CĐ)", "Chiều dài (m)"],
                        ["Phân đoạn 1", "C1", "1.7"],
                        ["Phân loại", "Phân đoạn", "Tên cọc (KT)",
                         "Chiều dài vết nứt L (m)"],
                        ["", "", "B3", "1,1"],
                        ["", "", "B4", "0,5"],
                        ["", "", "H6", "1"],
                        ["Nhóm 2", "Phân đoạn 1", "", ""],
                    ],
                }, ensure_ascii=False),
            ),
            PageExtraction(
                id="ext-exact-p9", project_id="p1", document_id=document.id,
                page_id=pages[1].id, page_number=9, model="test",
                prompt_version="p9", mode="direct", status="proposed",
                extraction_json=json.dumps({
                    "title": "MẶT BẰNG NHÓM CỌC NHÓM 2 (2/7)",
                    "summary": "Bố trí nhóm cọc 2, phân đoạn 3 - cầu chính.",
                    "drawing_number": "TK-03",
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
                id="ext-exact-p25", project_id="p1", document_id=document.id,
                page_id=pages[2].id, page_number=25, model="test",
                prompt_version="register", mode="direct", status="proposed",
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

    body = _chat(client, "cầu chính, cọc nhóm 2 cần sửa gồm những cọc nào")

    answer = body["answer"]
    assert body["no_source"] is False
    assert answer_provider.calls == []
    assert "3 mã đã xác minh" in answer
    assert "8 mã AI trích xuất chưa xác minh" in answer
    assert "chưa phải tổng chính thức" in answer
    assert "chưa xác minh" in answer
    # Non-source CĐ rows and OCR variants of already verified rows are not
    # promoted into the answer.
    assert not {"C1", "C3", "B3", "B4", "H6"} & set(answer.replace(",", " ").split())
    proposed_line = next(
        line for line in answer.splitlines()
        if "AI trích xuất, chưa xác minh —" in line
    )
    assert "I113" not in proposed_line and "I135" not in proposed_line
    assert "B184" not in proposed_line
    codes = [
        code.strip()
        for code in proposed_line.split("): ", 1)[1].rsplit(" [", 1)[0].split(",")
    ]
    assert set(codes) == {
        "I111", "I133", "I136", "H134", "G122", "G98", "F108", "B164"
    }
    assert len(codes) == len(set(codes)) == 8
    assert {citation["page_number"] for citation in body["citations"]} == {8, 9}
    page9 = next(
        citation for citation in body["citations"] if citation["page_number"] == 9
    )
    assert page9["drawing_number"] == "TK-03"
    assert "I133 | 0,7" in page9["quote"]
    page8 = next(
        citation for citation in body["citations"] if citation["page_number"] == 8
    )
    assert "hư hỏng" in page8["quote"]
    assert any("F108" in warning and "F106" in warning for warning in body["warnings"])


def test_same_proposed_pile_in_two_segments_is_not_assigned(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(
            db, suffix="ambiguous-segment", page_numbers=(9,)
        )
        db.add(PageExtraction(
            id="ext-ambiguous-segment", project_id="p1",
            document_id=document.id, page_id=pages[0].id, page_number=9,
            model="test", prompt_version="ambiguous", mode="direct",
            status="proposed", extraction_json=json.dumps({
                "title": "MẶT BẰNG NHÓM CỌC NHÓM 2 (2/7)",
                "summary": "Bố trí nhóm cọc 2 - cầu chính.",
                "table_rows": [
                    ["Phân loại", "Phân đoạn", "Tên cọc (KS)", "Chiều dài (m)"],
                    ["Nhóm 2", "Phân đoạn 3", "I133", "0,7"],
                    ["Nhóm 2", "Phân đoạn 4", "I133", "0,9"],
                ],
            }, ensure_ascii=False),
        ))
        db.commit()

    body = _chat(client, "cầu chính, cọc nhóm 2 cần sửa gồm những cọc nào")

    assert body["no_source"] is True
    assert body["citations"] == []
    assert "I133" not in body["answer"]
    assert any("I133" in warning for warning in body["warnings"])
    assert answer_provider.calls == []


def test_group_answer_keeps_approach_codes_out_of_main_bridge(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        main, main_pages = _document(db, suffix="main-group", page_numbers=(9,))
        db.add(PageExtraction(
            id="ext-main-group", project_id="p1", document_id=main.id,
            page_id=main_pages[0].id, page_number=9, model="test",
            prompt_version="main", mode="direct", status="proposed",
            extraction_json=json.dumps({
                "title": "MẶT BẰNG NHÓM CỌC NHÓM 2 (2/7)",
                "table_rows": [
                    ["Phân loại", "Phân đoạn", "Tên cọc (KS)", "Chiều dài (m)"],
                    ["Nhóm 2", "Phân đoạn 3", "I133", "0,7"],
                ],
            }, ensure_ascii=False),
        ))
        approach, approach_pages = _document(
            db, suffix="approach-group", page_numbers=(11,)
        )
        db.add(PageExtraction(
            id="ext-approach-group", project_id="p1", document_id=approach.id,
            page_id=approach_pages[0].id, page_number=11, model="test",
            prompt_version="approach", mode="direct", status="proposed",
            extraction_json=json.dumps({
                "title": "MẶT BẰNG NHÓM CỌC NHÓM 2 (4/7)",
                "summary": "Ba mặt bằng nhóm cọc số 2 của cầu dẫn.",
                "table_rows": [
                    ["Phân loại", "Phân đoạn", "Vị trí", "Tên cọc (KS)",
                     "Chiều dài (m)"],
                    ["Nhóm 2", "Phân đoạn 11", "Cầu dẫn", "Q292", "1,1"],
                    ["", "", "", "Q288", "0,8"],
                ],
            }, ensure_ascii=False),
        ))
        db.commit()

    body = _chat(client, "cọc nhóm 2 cần sửa ở cầu dẫn")

    assert body["no_source"] is False
    assert answer_provider.calls == []
    assert "Q292" in body["answer"] and "Q288" in body["answer"]
    assert "I133" not in body["answer"]
    assert "Chưa có mã nào đã xác minh" in body["answer"]
    assert {citation["page_number"] for citation in body["citations"]} == {11}


def test_pile_location_prefers_verified_fact_and_avoids_measurement_dump(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="location-verified", page_numbers=(8,))
        _extraction(db, document, pages[0], "location-verified", [
            _fact("F27", "chiều sâu đục", "1", "cm", group="Nhóm 2", segment="Phân đoạn 1")
        ])
        db.commit()
    body = _chat(client, "Cọc F27 thuộc nhóm mấy, ở phân đoạn nào?")
    assert body["no_source"] is False
    assert "Nhóm 2, Phân đoạn 1, Cầu chính" in body["answer"]
    assert "chiều sâu đục" not in body["answer"]
    assert body["citations"][0]["page_number"] == 8


def test_pile_location_labels_numeric_segment_and_omits_unknown_location(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="location-partial", page_numbers=(8,))
        _extraction(db, document, pages[0], "location-partial", [
            _fact("Q295", "chiều sâu đục", "1", "cm", group="2", segment="1", location="")
        ])
        db.commit()
    body = _chat(client, "Cọc Q295 thuộc nhóm mấy và ở đâu?")
    assert "Nhóm 2, Phân đoạn 1 [1]" in body["answer"]
    assert ",  " not in body["answer"]
    assert "chưa ghi rõ vị trí" in body["warnings"][0]


def test_pile_location_uses_exact_proposed_plan_row(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="location-plan", page_numbers=(7,))
        db.add(PageExtraction(
            id="ext-location-plan", project_id="p1", document_id=document.id,
            page_id=pages[0].id, page_number=7, model="test", prompt_version="plan",
            mode="direct", status="proposed", extraction_json=json.dumps({
                "title": "MẶT BẰNG NHÓM CỌC NHÓM 2",
                "table_rows": [
                    ["Phân loại", "Phân đoạn", "Vị trí", "Tên cọc (KS)"],
                    ["Nhóm 2", "Phân đoạn 1", "Cầu chính", "F27"],
                    ["", "", "", "F270"],
                ],
            }, ensure_ascii=False),
        ))
        db.commit()
    body = _chat(client, "Cọc F27 thuộc nhóm mấy, ở đâu?")
    assert "Nhóm 2, Phân đoạn 1, Cầu chính" in body["answer"]
    assert "chưa được kỹ sư xác minh" in body["answer"]
    assert body["citations"][0]["page_number"] == 7
    assert _chat(client, "Cọc F2 thuộc nhóm mấy?")["no_source"] is True


def test_beam_location_uses_exact_proposed_plan_row(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="beam-location", page_numbers=(103,))
        db.add(PageExtraction(
            id="ext-beam-location", project_id="p1", document_id=document.id,
            page_id=pages[0].id, page_number=103, model="test", prompt_version="beam-plan",
            mode="direct", status="proposed", extraction_json=json.dumps({
                "title": "MẶT BẰNG, KÝ HIỆU VÀ PHÂN NHÓM SỬA CHỮA - CẦU DẪN",
                "table_rows": [
                    ["Phân nhóm", "Phân đoạn", "Ký hiệu dầm", "Loại dầm"],
                    ["1", "PĐ12", "Q-295", "Dầm ngang"],
                ],
            }, ensure_ascii=False),
        ))
        db.commit()
    body = _chat(client, "Dầm Q-295 thuộc nhóm mấy, ở đâu?")
    assert "Nhóm 1, Phân đoạn 12, Cầu dẫn, Dầm ngang" in body["answer"]
    assert "chưa được kỹ sư xác minh" in body["answer"]
    assert body["citations"][0]["page_number"] == 103
    assert _chat(client, "Dầm Q-296 ở đâu?")["no_source"] is True


def test_procedure_query_refuses_when_only_dimensions_are_verified(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="procedure", page_numbers=(22,))
        _extraction(db, document, pages[0], "procedure", [
            _fact("H77", "chiều sâu đục", "1", "cm")
        ])
        db.commit()
    body = _chat(client, "Quy trình xử lý cọc H77 là gì?")
    assert body["no_source"] is True
    assert body["citations"] == []


def test_procedure_joins_member_group_to_report_with_both_citations(client, session_factory):
    with session_factory() as db:
        drawing, drawing_pages = _document(db, suffix="member", page_numbers=(7,))
        _extraction(db, drawing, drawing_pages[0], "member", [
            _fact("H77", "nhóm", "1", "nhóm")
        ])
        report, report_pages = _document(db, suffix="process", page_numbers=(32,))
        _extraction(db, report, report_pages[0], "process", [
            _fact("PILE-GROUP-1", "quy trình xử lý theo nhóm", "Đục và quét keo", "quy trình")
        ])
        db.commit()
    body = _chat(client, "Quy trình xử lý cọc H77 là gì?")
    assert body["no_source"] is False
    assert "Đục và quét keo" in body["answer"]
    assert "Áp dụng theo phân loại nhóm của H77" in body["answer"]
    assert {citation["page_number"] for citation in body["citations"]} == {7, 32}


def test_beam_fiber_area_shows_calculated_formula(client, session_factory):
    with session_factory() as db:
        document, pages = _document(db, suffix="fiber", page_numbers=(46,))
        facts = [_fact("I-30-31", "tổng diện tích dán sợi", "4,560", "m²", component_type="beam")]
        for panel, length, width, count in (
            ("T1", "1.9", "0.2", "4"),
            ("T2", "1.6", "0.25", "7"),
            ("T3", "1.6", "0.15", "1"),
        ):
            for name, value, unit in (
                (f"chiều dài tấm {panel} dán sợi", length, "m"),
                (f"chiều rộng tấm {panel} dán sợi", width, "m"),
                (f"số tấm {panel}", count, "tấm"),
            ):
                facts.append(_fact("I-30-31", name, value, unit, component_type="beam"))
        _extraction(db, document, pages[0], "fiber", facts)
        db.commit()
    body = _chat(client, "Dầm I-30-31 diện tích dán sợi bao nhiêu?")
    assert "tổng diện tích dán sợi: 4,560 m²" in body["answer"]
    assert "A = Σ(L × W × số tấm)" in body["answer"]
    assert "T1 (1.9 m × 0.2 m × 4)" in body["answer"]
    assert "T2 (1.6 m × 0.25 m × 7)" in body["answer"]
    assert "T3 (1.6 m × 0.15 m × 1)" in body["answer"]
    assert "= 4.560 m²" in body["answer"]


def test_component_citation_uses_verified_extraction_metadata(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="meta")
        document.drawing_number = "CHI"
        document.revision = "CHI"
        pages[0].drawing_number = None
        pages[0].revision = None
        _extraction(
            db,
            document,
            pages[0],
            "meta",
            [_fact("H77", "chiều sâu đục", "1", "cm")],
            drawing_number="TK-16",
            revision="B",
        )

        fallback, fallback_pages = _document(db, suffix="meta-fallback")
        fallback.drawing_number = "CHI"
        fallback.revision = "CHI"
        fallback_pages[0].drawing_number = None
        fallback_pages[0].revision = None
        _extraction(
            db,
            fallback,
            fallback_pages[0],
            "meta-fallback",
            [_fact("H78", "chiều sâu đục", "2", "cm")],
        )
        db.commit()

    body = _chat(client, "Cọc H77 đục sâu bao nhiêu?")
    citation = body["citations"][0]
    assert citation["drawing_number"] == "TK-16"
    assert citation["revision"] == "B"

    fallback_body = _chat(client, "Cọc H78 đục sâu bao nhiêu?")
    fallback_citation = fallback_body["citations"][0]
    assert fallback_citation["drawing_number"] is None
    assert fallback_citation["revision"] is None


def test_proposed_fact_is_not_trusted_or_replaced_by_generic_chat(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="p02")
        _extraction(
            db,
            document,
            pages[0],
            "p02",
            [_fact("P-02", "chiều sâu đục", "9", "cm")],
            status="proposed",
        )
        db.commit()

    body = _chat(client, "Cọc P-02 đục sâu bao nhiêu?")

    assert body["answer"] == NO_SOURCE_ANSWER
    assert body["no_source"] is True
    assert body["citations"] == []
    assert answer_provider.calls == []


def test_non_effective_and_foreign_project_facts_are_refused(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        old, old_pages = _document(db, suffix="old", effective=False)
        _extraction(db, old, old_pages[0], "old", [_fact("H88", "đục sâu", "2", "cm")])
        foreign, foreign_pages = _document(db, project_id="p2", suffix="foreign")
        _extraction(
            db, foreign, foreign_pages[0], "foreign", [_fact("H99", "đục sâu", "3", "cm")]
        )
        db.commit()

    for message in ("Cọc H88 đục sâu bao nhiêu?", "Cọc H99 đục sâu bao nhiêu?"):
        body = _chat(client, message)
        assert body["answer"] == NO_SOURCE_ANSWER
        assert body["no_source"] is True
        assert body["citations"] == []
    assert answer_provider.calls == []


def test_location_segment_lists_all_groups_with_citations(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(
            db, suffix="groups", page_numbers=(8, 15)
        )
        _extraction(
            db,
            document,
            pages[0],
            "group2",
            [
                _fact(
                    "H77",
                    "tình trạng",
                    "hư hỏng",
                    "",
                    group="Nhóm 2",
                    segment="Phân đoạn 1",
                ),
                _fact(
                    "I3",
                    "tình trạng",
                    "hư hỏng",
                    "",
                    group="Nhóm 2",
                    segment="Phân đoạn 1",
                ),
            ],
        )
        _extraction(
            db,
            document,
            pages[1],
            "group3",
            [
                _fact(
                    "A150",
                    "tình trạng",
                    "hư hỏng",
                    "",
                    group="Nhóm 3",
                    segment="Phân đoạn 1",
                )
            ],
        )
        db.commit()

    body = _chat(client, "Cầu chính phân đoạn 1 các cọc nào hỏng?")

    assert body["no_source"] is False
    assert "Nhóm 2" in body["answer"]
    assert "Nhóm 3" in body["answer"]
    assert "H77" in body["answer"] and "I3" in body["answer"]
    assert "A150" in body["answer"]
    assert "Đã xác minh: 3 cấu kiện trong 2 nhóm." in body["answer"]
    assert "có thể chưa đầy đủ" in body["answer"]
    assert "Tổng:" not in body["answer"]
    assert {citation["page_number"] for citation in body["citations"]} == {8, 15}
    assert answer_provider.calls == []

    filtered = _chat(client, "Cầu chính phân đoạn 1 nhóm 3 cọc nào hỏng?")
    assert "Nhóm 3" in filtered["answer"]
    assert "Nhóm 2" not in filtered["answer"]
    assert "A150" in filtered["answer"]


def test_segment_without_location_lists_each_location_with_citations(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="locations", page_numbers=(8, 9))
        _extraction(db, document, pages[0], "main", [
            _fact("H77", "tình trạng", "hư hỏng", "", segment="Phân đoạn 1")
        ])
        _extraction(db, document, pages[1], "approach", [
            _fact("D10", "tình trạng", "hư hỏng", "", segment="Phân đoạn 1", location="Cầu dẫn")
        ])
        db.commit()

    body = _chat(client, "phân đoạn một cần sửa những cọc nào")

    assert body["no_source"] is False
    assert "Cầu chính, Nhóm 1" in body["answer"]
    assert "Cầu dẫn, Nhóm 1" in body["answer"]
    assert "H77" in body["answer"] and "D10" in body["answer"]
    assert "không nêu vị trí" in body["answer"]
    assert {citation["page_number"] for citation in body["citations"]} == {8, 9}
    assert answer_provider.calls == []


def test_direct_quantity_is_not_recomputed_from_dimensions(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="direct")
        _extraction(
            db,
            document,
            pages[0],
            "direct",
            [
                _fact("H77", "chiều dài quét keo", "2", "m"),
                _fact("H77", "chiều rộng quét keo", "1", "m"),
                _fact("H77", "diện tích quét keo", "3", "m²"),
            ],
        )
        db.commit()

    body = _chat(client, "Cọc H77 diện tích quét keo bao nhiêu?")

    assert "diện tích quét keo: 3 m²" in body["answer"]
    assert "hệ thống tính" not in body["answer"]
    assert "2 m²" not in body["answer"]
    assert answer_provider.calls == []


def test_direct_quantity_is_specific_to_requested_work(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="work")
        _extraction(
            db,
            document,
            pages[0],
            "work",
            [
                _fact("H77", "diện tích đục", "0.010", "m²"),
                _fact("H77", "diện tích quét keo", "0.304", "m²"),
            ],
        )
        db.commit()

    chiseled = _chat(client, "Cọc H77 diện tích đục bao nhiêu?")
    assert "diện tích đục: 0.010 m²" in chiseled["answer"]
    assert "0.304" not in chiseled["answer"]

    glued = _chat(client, "Cọc H77 diện tích quét keo bao nhiêu?")
    assert "diện tích quét keo: 0.304 m²" in glued["answer"]
    assert "0.010" not in glued["answer"]


def test_missing_work_specific_direct_quantity_is_refused(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="work-missing")
        _extraction(
            db,
            document,
            pages[0],
            "work-missing",
            [_fact("H77", "diện tích quét keo", "0.304", "m²")],
        )
        db.commit()

    body = _chat(client, "Cọc H77 diện tích đục bao nhiêu?")

    assert body["answer"] == NO_SOURCE_ANSWER
    assert body["no_source"] is True
    assert body["citations"] == []
    assert any("công tác khác" in warning for warning in body["warnings"])
    assert answer_provider.calls == []


def test_ambiguous_decimal_thousands_separator_is_rejected():
    assert _dimension_value("1.280") is None
    assert _dimension_value("1,280") is None
    assert _dimension_value("1280") == 1280
    assert _dimension_value("1.28") == 1.28
    assert _dimension_value("0.003") == 0.003


def test_ambiguous_dimension_does_not_produce_computed_volume(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="ambiguous")
        _extraction(
            db,
            document,
            pages[0],
            "ambiguous",
            [
                _fact("H77", "chiều dài đục", "2", "m"),
                _fact("H77", "chiều rộng đục", "1", "m"),
                _fact("H77", "chiều sâu đục", "1.280", "m"),
            ],
        )
        db.commit()

    body = _chat(client, "Cọc H77 thể tích đục bao nhiêu?")

    assert "hệ thống tính" not in body["answer"]
    assert "m³" not in body["answer"]
    assert "không tự suy ra từ một kích thước" in body["answer"]
    assert answer_provider.calls == []


def test_volume_with_missing_dimensions_is_refused(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="missing")
        _extraction(
            db,
            document,
            pages[0],
            "missing",
            [_fact("H77", "chiều dài đục", "2", "m")],
        )
        db.commit()

    body = _chat(client, "Cọc H77 thể tích đục bao nhiêu?")

    assert "hệ thống tính" not in body["answer"]
    assert "m³" not in body["answer"]
    assert "không tự suy ra từ một kích thước" in body["answer"]
    assert answer_provider.calls == []


def test_complete_dimensions_compute_volume_with_quantity_calc(
    client, session_factory, answer_provider
):
    with session_factory() as db:
        document, pages = _document(db, suffix="computed")
        _extraction(
            db,
            document,
            pages[0],
            "computed",
            [
                _fact("H77", "chiều dài đục", "200", "cm"),
                _fact("H77", "chiều rộng đục", "100", "cm"),
                _fact("H77", "chiều sâu đục", "50", "cm"),
            ],
        )
        db.commit()

    body = _chat(client, "Cọc H77 thể tích đục bao nhiêu?")

    assert "Thể tích (hệ thống tính): V = L × W × D" in body["answer"]
    assert "V = 2 m × 1 m × 0.5 m = 1 m³" in body["answer"]
    assert "hồ sơ ghi sẵn (trực tiếp)" in body["answer"]
    assert any("Giá trị tính được tách" in warning for warning in body["warnings"])
    assert answer_provider.calls == []


def test_mixed_revisions_are_not_combined(client, session_factory, answer_provider):
    with session_factory() as db:
        first, first_pages = _document(db, suffix="rev-a", revision="A")
        _extraction(
            db, first, first_pages[0], "rev-a", [_fact("H77", "chiều sâu đục", "1", "cm")]
        )
        second, second_pages = _document(db, suffix="rev-b", revision="B")
        _extraction(
            db, second, second_pages[0], "rev-b", [_fact("H77", "chiều sâu đục", "2", "cm")]
        )
        db.commit()

    body = _chat(client, "Cọc H77 đục sâu bao nhiêu?")

    assert body["answer"] == NO_SOURCE_ANSWER
    assert body["no_source"] is True
    assert body["citations"] == []
    assert any("revision" in warning for warning in body["warnings"])
    assert answer_provider.calls == []
