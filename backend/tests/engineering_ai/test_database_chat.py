"""Database chat path: whole-token codes, no full-project dump, citations."""

from datetime import date, datetime, timezone

from app.core.component_models import (
    ComponentAlias,
    ComponentDesignParameter,
    ComponentStage,
    DesignGroup,
    ProgressEvent,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.engineering_ai.database_chat import _matched_components, answer_structured_question
from app.engineering_ai.providers import ExtractiveProvider


def _utc_now():
    return datetime.now(timezone.utc)


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


def _seed_progress(db):
    zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
    db.add(zone)
    db.flush()
    segment = Segment(zone_id=zone.id, number=2, source_code="PD2")
    db.add(segment)
    db.flush()
    group = DesignGroup(
        project_id="p1",
        group_type="PILE_REPAIR_CLASS",
        name="Nhóm 2",
        drawing="TK-02",
        source="seed",
    )
    db.add(group)
    db.flush()
    components = []
    for code in ("F67", "F68", "F69"):
        component = StructuralComponent(
            project_id="p1",
            segment_id=segment.id,
            design_group_id=group.id,
            type="pile",
            raw_code=code,
            canonical_code=code,
            verification="verified",
            created_by="u1",
        )
        db.add(component)
        components.append(component)
    db.flush()
    chip = StageDefinition(
        project_id="p1", component_type="pile", code="DUC", name="Đục bê tông", position=0
    )
    glue = StageDefinition(
        project_id="p1", component_type="pile", code="SON", name="Sơn bảo vệ", position=1
    )
    db.add_all([chip, glue])
    db.flush()
    chip_stages = []
    for component in components:
        stage = ComponentStage(
            component_id=component.id,
            stage_definition_id=chip.id,
            repair_scope_id="scope-1",
            created_by="u1",
        )
        db.add(stage)
        chip_stages.append(stage)
    glue_stage = ComponentStage(
        component_id=components[0].id,
        stage_definition_id=glue.id,
        repair_scope_id="scope-1",
        created_by="u1",
    )
    db.add(glue_stage)
    db.flush()
    db.add_all(
        [
            ProgressEvent(
                component_id=components[0].id,
                component_stage_id=chip_stages[0].id,
                event_date=date(2026, 11, 21),
                status="COMPLETED",
                quantity=0.3,
                unit="m3",
            ),
            ProgressEvent(
                component_id=components[1].id,
                component_stage_id=chip_stages[1].id,
                event_date=date(2026, 11, 21),
                status="IN_PROGRESS",
                quantity=0.2,
                unit="m3",
            ),
            ProgressEvent(
                component_id=components[0].id,
                component_stage_id=glue_stage.id,
                event_date=date(2026, 11, 20),
                status="IN_PROGRESS",
            ),
        ]
    )
    db.commit()
    return components


def _seed_design_parameters(db):
    zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
    db.add(zone)
    db.flush()
    segment = Segment(zone_id=zone.id, number=2, source_code="PD2")
    db.add(segment)
    db.flush()
    components = {}
    for code in ("F67", "F68", "H65", "B153"):
        component = StructuralComponent(
            project_id="p1",
            segment_id=segment.id,
            type="pile",
            raw_code=code,
            canonical_code=code,
            verification="verified",
            created_by="u1",
        )
        db.add(component)
        components[code] = component
    db.flush()
    values = {
        "F67": {"t_cm": 3, "L1_m": 4.5, "n": 2, "a_mm": 100, "b_mm": 150},
        "F68": {"t_cm": 5, "L1_m": 5.0},
        "H65": {"L1_m": 6.0},
        "B153": {"t_cm": 5, "L2_m": 2.5},
    }
    for code, params in values.items():
        for name, value in params.items():
            unit = "cm" if name == "t_cm" else "m" if name.endswith("_m") else "mm" if name.endswith("_mm") else ""
            db.add(
                ComponentDesignParameter(
                    project_id="p1",
                    component_id=components[code].id,
                    name=name,
                    value=float(value),
                    unit=unit,
                    source_drawing="TK-19",
                    source_page=23,
                    source_row=14 if code == "F67" else 20,
                    source_file_hash="a" * 64,
                    created_by="u1",
                )
            )
    db.commit()
    return components



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


def test_chat_answers_design_thickness_with_source_citation(client, session_factory):
    with session_factory() as db:
        _seed_design_parameters(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "Cọc F67 đục dày bao nhiêu?"},
    ).json()
    assert body["no_source"] is False
    assert "t = 3 cm" in body["answer"]
    citation = body["citations"][0]
    assert citation["source"] == "database"
    assert citation["record_id"]
    assert citation["drawing_number"] == "TK-19"
    assert citation["page_number"] == 23
    assert citation["section"] == "dòng 14"


def test_chat_says_missing_t_instead_of_guessing(client, session_factory):
    with session_factory() as db:
        _seed_design_parameters(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "chiều dày t của H65"},
    ).json()
    assert body["no_source"] is False
    assert "chưa có số liệu t trong bảng thiết kế" in body["answer"]
    assert any("không suy đoán" in warning for warning in body["warnings"])
    assert body["citations"]


def test_chat_lists_all_design_parameters(client, session_factory):
    with session_factory() as db:
        _seed_design_parameters(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "thông số cọc B153"},
    ).json()
    assert body["no_source"] is False
    assert "t = 5 cm" in body["answer"]
    assert "L2 = 2.5 m" in body["answer"]
    assert all(citation["drawing_number"] == "TK-19" for citation in body["citations"])


def test_chat_finds_components_by_thickness_value_for_segment(client, session_factory):
    with session_factory() as db:
        _seed_design_parameters(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "PD2 cọc nào t = 5 cm"},
    ).json()
    assert body["no_source"] is False
    assert "2 cọc" in body["answer"]
    assert "F68" in body["answer"] and "B153" in body["answer"]
    assert "F67" not in body["answer"] and "H65" not in body["answer"]
    assert len(body["citations"]) == 2
    assert all(citation["page_number"] == 23 for citation in body["citations"])


def test_chat_finds_components_by_thickness_range_for_segment(client, session_factory):
    with session_factory() as db:
        _seed_design_parameters(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "PD2 cọc nào t từ 3 đến 5 cm"},
    ).json()
    assert body["no_source"] is False
    assert "3 cọc" in body["answer"]
    assert "F67" in body["answer"]
    assert "F68" in body["answer"] and "B153" in body["answer"]
    assert "H65" not in body["answer"]


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


def test_chat_answers_pending_stage_count_for_segment(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)

    response = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "PD2 còn bao nhiêu cọc chưa đục bê tông?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["no_source"] is False
    assert "2/3 cọc" in body["answer"]
    assert "Đục bê tông" in body["answer"]
    assert body["citations"]
    assert all(citation["source"] == "database" for citation in body["citations"])


def test_chat_answers_daily_progress_for_date_and_segment(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)

    response = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "Tiến độ ngày 21/11 PD2"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["no_source"] is False
    assert "21/11/2026" in body["answer"]
    assert "PD2" in body["answer"]
    assert "F67" in body["answer"] and "F68" in body["answer"]
    assert "COMPLETED" in body["answer"] and "IN_PROGRESS" in body["answer"]
    assert "không phải nghiệm thu" in body["answer"]
    assert all(citation["source"] == "database" for citation in body["citations"])


def test_chat_answers_latest_progress_date(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "Tiến độ ngày gần nhất?"},
    ).json()
    assert body["no_source"] is False
    assert "21/11/2026" in body["answer"]
    assert "F67" in body["answer"]


def test_chat_answers_bare_date_and_segment_question(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "21/11 PD2 có gì?"},
    ).json()
    assert body["no_source"] is False
    assert "21/11/2026" in body["answer"]
    assert "F68" in body["answer"]


def test_chat_answers_date_question_without_segment(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "Ngày 21/11 làm gì?"},
    ).json()
    assert body["no_source"] is False
    assert "21/11/2026" in body["answer"]
    assert "F67" in body["answer"]


def test_chat_ignores_voided_progress_events(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)
        from sqlalchemy import select

        from app.core.component_models import ComponentStage, ProgressEvent as Event

        f69 = db.scalar(
            select(StructuralComponent).where(
                StructuralComponent.project_id == "p1",
                StructuralComponent.canonical_code == "F69",
            )
        )
        stage = db.scalar(
            select(ComponentStage).where(ComponentStage.component_id == f69.id)
        )
        db.add(
            Event(
                component_id=f69.id,
                component_stage_id=stage.id,
                event_date=date(2026, 11, 22),
                status="COMPLETED",
                voided_at=_utc_now(),
                void_reason="Nhập trùng",
            )
        )
        db.commit()

    latest = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "Tiến độ ngày gần nhất?"},
    ).json()
    assert latest["no_source"] is False
    assert "21/11/2026" in latest["answer"]
    assert "F69" not in latest["answer"]
    assert "22/11/2026" not in latest["answer"]

    pending = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "PD2 còn bao nhiêu cọc chưa đục bê tông?"},
    ).json()
    assert "2/3 cọc" in pending["answer"]


def test_suggestions_ignore_voided_progress_and_keep_latest_date(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)
        from sqlalchemy import select

        from app.core.component_models import ComponentStage, ProgressEvent as Event

        f68 = db.scalar(
            select(StructuralComponent).where(
                StructuralComponent.project_id == "p1",
                StructuralComponent.canonical_code == "F68",
            )
        )
        stage = db.scalar(
            select(ComponentStage).where(ComponentStage.component_id == f68.id)
        )
        db.add(
            Event(
                component_id=f68.id,
                component_stage_id=stage.id,
                event_date=date(2026, 12, 5),
                status="IN_PROGRESS",
                voided_at=_utc_now(),
            )
        )
        db.commit()

    chips = client.get("/api/v1/projects/p1/ai/question-suggestions").json()
    prompts = " | ".join(chip["prompt"] for chip in chips)
    assert "21/11" in prompts
    assert "05/12" not in prompts and "5/12" not in prompts



def test_chat_answers_current_component_stage(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)

    body = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "Cọc F67 đang ở bước nào?"},
    ).json()
    assert body["no_source"] is False
    assert "F67" in body["answer"]
    assert "Đục bê tông" in body["answer"]
    assert "COMPLETED" in body["answer"]
    assert body["citations"]


def test_question_suggestions_come_from_project_data(client, session_factory):
    with session_factory() as db:
        _seed_progress(db)

    response = client.get("/api/v1/projects/p1/ai/question-suggestions")
    assert response.status_code == 200, response.text
    chips = response.json()
    assert 4 <= len(chips) <= 5
    prompts = " | ".join(chip["prompt"] for chip in chips)
    assert "PD2" in prompts
    assert "F67" in prompts
    assert "Tiến độ ngày" in prompts
    assert "Mở bản vẽ" in prompts
    assert "H77" not in prompts
    assert all(chip["mode"] in {"send", "fill"} for chip in chips)


def test_question_suggestions_empty_without_components(client):
    assert client.get("/api/v1/projects/p1/ai/question-suggestions").json() == []

