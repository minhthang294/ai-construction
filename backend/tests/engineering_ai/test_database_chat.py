"""Database chat path: whole-token codes, no full-project dump, citations."""

from app.core.component_models import (
    ComponentAlias,
    Segment,
    StructuralComponent,
    StructureZone,
)
from app.engineering_ai.database_chat import _matched_components, answer_structured_question
from app.engineering_ai.providers import ExtractiveProvider


def _seed(db, count=30):
    zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
    db.add(zone)
    db.flush()
    segment = Segment(zone_id=zone.id, number=1, source_code="PD1")
    db.add(segment)
    db.flush()
    components = []
    for index in range(1, count + 1):
        component = StructuralComponent(
            project_id="p1",
            segment_id=segment.id,
            type="pile",
            raw_code=f"P{index:03d}",
            canonical_code=f"P{index:03d}",
            verification="verified",
            created_by="u1",
        )
        db.add(component)
        components.append(component)
    db.commit()
    return components


def _ask(db, message):
    return answer_structured_question(
        db, "p1", message, 6, ExtractiveProvider(), "effective"
    )


def test_component_matching_is_whole_token(session_factory):
    with session_factory() as db:
        zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
        db.add(zone)
        db.flush()
        segment = Segment(zone_id=zone.id, number=1, source_code="PD1")
        db.add(segment)
        db.flush()
        a2 = StructuralComponent(
            project_id="p1", segment_id=segment.id, type="pile", raw_code="A2",
            canonical_code="A2", verification="verified", created_by="u1",
        )
        a23 = StructuralComponent(
            project_id="p1", segment_id=segment.id, type="pile", raw_code="A23",
            canonical_code="A23", verification="verified", created_by="u1",
        )
        long_code = StructuralComponent(
            project_id="p1", segment_id=segment.id, type="pile", raw_code="I-42",
            canonical_code="I-42", verification="verified", created_by="u1",
        )
        db.add_all([a2, a23, long_code])
        db.flush()
        db.add(
            ComponentAlias(
                component_id=long_code.id,
                project_id="p1",
                segment_id=segment.id,
                type="pile",
                alias="I40-42",
            )
        )
        db.commit()

        assert _matched_components([a2, a23, long_code], {}, "Cấu kiện A23 đục sâu") == [a23]
        alias_match = _matched_components(
            [a2, a23, long_code], {long_code.id: ["I40-42"]}, "Cọc I-40-42 ở đâu?"
        )
        assert alias_match == [long_code]
        assert a2 not in _matched_components([a2, a23], {}, "A23")


def test_aggregate_answer_does_not_dump_the_whole_project(session_factory):
    with session_factory() as db:
        _seed(db)
        answer, citations, warnings, no_source, _confidence = _ask(
            db, "Có bao nhiêu cấu kiện trong công trình?"
        )

    assert no_source is False
    assert answer.text and "30 cấu kiện" in answer.text
    assert 1 <= len(citations) <= 5
    assert all(citation.record_id and citation.source == "database" for citation in citations)
    assert "P030" not in answer.text
    assert any("không phải nghiệm thu" in warning for warning in warnings)


def test_unmatched_code_asks_for_specific_code_instead_of_dumping(session_factory):
    with session_factory() as db:
        _seed(db)
        answer, citations, warnings, no_source, _confidence = _ask(
            db, "Cấu kiện Z999 đục sâu bao nhiêu?"
        )

    assert no_source is True
    assert answer.text == "Không tìm thấy thông tin này trong hồ sơ công trình hiện có."
    assert citations == []
    assert any("Không tìm thấy mã z999" in warning for warning in warnings)
    assert any("mã cấu kiện cụ thể" in warning for warning in warnings)


def test_chat_exact_code_falls_back_to_component_database(client, session_factory):
    with session_factory() as db:
        _seed(db, count=1)

    response = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "Cọc P001 đục sâu bao nhiêu?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["no_source"] is False
    assert "P001" in body["answer"]
    assert body["citations"]
    assert body["citations"][0]["source"] == "database"
    assert body["citations"][0]["record_id"]
    assert any("không phải nghiệm thu" in warning for warning in body["warnings"])
