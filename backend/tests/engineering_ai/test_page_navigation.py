import json

from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument
from app.engineering_ai.page_navigation import parse_page_navigation_query


def _document(
    db,
    *,
    document_id,
    document_type,
    name,
    page_numbers,
    drawing_number=None,
):
    document = SourceDocument(
        id=document_id,
        project_id="p1",
        type=document_type,
        original_name=name,
        document_key=document_id,
        original_path=f"/tmp/{document_id}.pdf",
        sha256=(document_id * 64)[:64],
        status="ready",
        is_current=True,
        is_effective=True,
        page_count=max(page_numbers),
        drawing_number=drawing_number,
    )
    pages = [
        DocumentPage(
            id=f"{document_id}-page-{number}",
            project_id="p1",
            document_id=document_id,
            page_number=number,
            drawing_number=drawing_number,
        )
        for number in page_numbers
    ]
    db.add_all([document, *pages])
    return document, {page.page_number: page for page in pages}


def _extraction(
    db,
    document,
    page,
    *,
    suffix,
    title,
    summary="",
    status="verified",
    facts=None,
):
    db.add(
        PageExtraction(
            id=f"{document.id}-{page.page_number}-{suffix}",
            project_id="p1",
            document_id=document.id,
            page_id=page.id,
            page_number=page.page_number,
            model="test",
            prompt_version=suffix,
            mode="direct",
            status=status,
            extraction_json=json.dumps(
                {
                    "title": title,
                    "summary": summary,
                    "component_facts": facts or [],
                },
                ensure_ascii=False,
            ),
        )
    )


def _pile_process(group="2"):
    return {
        "component_type": "pile",
        "component_code": f"PILE-GROUP-{group}",
        "fact_name": "quy trình xử lý theo nhóm",
        "value": "Đục bê tông, vệ sinh, quét keo epoxy, bơm vữa, dán sợi carbon.",
        "unit": "quy trình",
        "quote": "Quy trình xử lý cọc theo nhóm.",
        "group": group,
        "location": "Cầu chính",
        "table_column": f"4.2. Công tác sửa chữa cọc — Cọc nhóm {group}",
    }


def _chat(client, message):
    response = client.post(
        "/api/v1/projects/p1/ai/chat", json={"message": message}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _seed(client, session_factory):
    with session_factory() as db:
        drawing, drawing_pages = _document(
            db,
            document_id="drawing",
            document_type="drawing",
            name="ban-ve.pdf",
            page_numbers=(7, 8, 15),
            drawing_number="TK-01",
        )
        _extraction(
            db,
            drawing,
            drawing_pages[7],
            suffix="verified",
            title="PHÂN ĐOẠN 2 - CẦU CHÍNH - NHÓM 1",
            summary="Mặt bằng nhóm cọc nhóm 1, phân đoạn 2 - cầu chính.",
        )
        _extraction(
            db,
            drawing,
            drawing_pages[8],
            suffix="verified",
            title="PHÂN ĐOẠN 1 - CẦU CHÍNH - NHÓM 2",
            summary="Trang 8 có phần phân đoạn 1 - cầu chính - nhóm 2.",
        )
        _extraction(
            db,
            drawing,
            drawing_pages[8],
            suffix="proposed",
            title="MẶT BẰNG NHÓM CỌC NHÓM 2 (1/7)",
            summary=(
                "Trang thể hiện 'PHÂN ĐOẠN 1 - CẦU CHÍNH - NHÓM 2' và "
                "'PHÂN ĐOẠN 2 - CẦU CHÍNH - NHÓM 2'."
            ),
            status="proposed",
        )
        _extraction(
            db,
            drawing,
            drawing_pages[15],
            suffix="verified",
            title="PHÂN ĐOẠN 1 - CẦU CHÍNH - NHÓM 3",
            summary="Trang 15 có phần phân đoạn 1 - cầu chính - nhóm 3.",
        )
        _extraction(
            db,
            drawing,
            drawing_pages[15],
            suffix="proposed",
            title="MẶT BẰNG NHÓM CỌC NHÓM 3 (1/6)",
            summary=(
                "Bố trí nhóm cọc 3 cho 'PHÂN ĐOẠN 1' và 'PHÂN ĐOẠN 2 - "
                "CẦU CHÍNH - NHÓM 3'."
            ),
            status="proposed",
        )

        specification, spec_pages = _document(
            db,
            document_id="spec",
            document_type="specification",
            name="thuyet-minh.pdf",
            page_numbers=(32, 33),
        )
        _extraction(
            db,
            specification,
            spec_pages[32],
            suffix="verified",
            title="Cọc nhóm 1",
            summary="4.2. Công tác sửa chữa cọc — Cọc nhóm 1.",
            facts=[_pile_process("2")],
        )
        _extraction(
            db,
            specification,
            spec_pages[33],
            suffix="verified",
            title="Dầm cầu chính nhóm 1",
            summary="4.3. Công tác sửa chữa dầm ngang, dầm dọc.",
            facts=[_pile_process("2")],
        )
        drawing_id = drawing.id
        specification_id = specification.id
        db.commit()
    return drawing_id, specification_id


def test_open_construction_method_group_2_returns_two_page_sequence(
    client, session_factory, answer_provider
):
    _drawing_id, specification_id = _seed(client, session_factory)

    body = _chat(client, "mở trang biện pháp thi công cho cọc nhóm 2")

    assert body["no_source"] is False
    assert answer_provider.calls == []
    assert "trang 32" in body["answer"].lower()
    assert "trang 33" in body["answer"].lower()
    assert "I3" not in body["answer"] and "I133" not in body["answer"]
    assert {citation["page_number"] for citation in body["citations"]} == {32, 33}
    assert body["page_action"]["document_id"] == specification_id
    assert body["page_action"]["page_number"] == 32
    assert any("thuyết minh" in warning for warning in body["warnings"])


def test_open_design_segment_2_without_group_lists_candidates(
    client, session_factory, answer_provider
):
    _seed(client, session_factory)

    body = _chat(client, "mở trang thiết kế cầu chính phân đoạn 2")

    assert body["no_source"] is False
    assert answer_provider.calls == []
    assert body["page_action"] is None
    assert {citation["page_number"] for citation in body["citations"]} == {7, 8, 15}
    assert "Trang 7" in body["answer"]
    assert "Trang 8" in body["answer"]
    assert "Trang 15" in body["answer"]
    assert "nhóm cọc" in body["answer"]


def test_open_design_segment_2_group_2_returns_page_8(
    client, session_factory, answer_provider
):
    drawing_id, _specification_id = _seed(client, session_factory)

    body = _chat(
        client, "mở trang thiết kế cầu chính phân đoạn 2 nhóm 2"
    )

    assert body["no_source"] is False
    assert answer_provider.calls == []
    assert [citation["page_number"] for citation in body["citations"]] == [8]
    assert body["page_action"]["document_id"] == drawing_id
    assert body["page_action"]["page_number"] == 8


def test_open_explicit_page_prefers_requested_document_type(
    client, session_factory
):
    drawing_id, _specification_id = _seed(client, session_factory)

    body = _chat(client, "mở trang 8 bản vẽ")

    assert body["no_source"] is False
    assert [citation["page_number"] for citation in body["citations"]] == [8]
    assert body["citations"][0]["document_id"] == drawing_id
    assert body["page_action"]["page_number"] == 8


def test_open_missing_page_refuses_without_autopick(
    client, session_factory, answer_provider
):
    _seed(client, session_factory)

    body = _chat(client, "mở trang 999")

    assert body["no_source"] is True
    assert body["citations"] == []
    assert body["page_action"] is None
    assert answer_provider.calls == []


def test_navigation_parser_does_not_hijack_factual_questions():
    assert parse_page_navigation_query("quy trình xử lý cọc nhóm 2 là gì?") is None
    assert parse_page_navigation_query("mở rộng cầu chính có ảnh hưởng gì?") is None
    assert parse_page_navigation_query("chiều dài cọc nhóm 2 là bao nhiêu?") is None
    query = parse_page_navigation_query("mở trang biện pháp thi công cho cọc nhóm 2")
    assert query is not None
    assert query.method is True
    assert query.group == "2"
    assert query.component_type == "pile"
