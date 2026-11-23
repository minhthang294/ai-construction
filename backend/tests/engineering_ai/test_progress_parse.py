"""Golden tests for the deterministic Zalo progress parser (read-only)."""

from datetime import date, timedelta
from typing import Dict

from app.core.component_models import (
    ComponentAlias,
    ComponentDesignParameter,
    ComponentStage,
    ConstructionBatch,
    ConstructionBatchComponent,
    ProgressEvent,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.engineering_ai.progress_parse import progress_parse

GOLDEN_MESSAGE = (
    "Cọc đục ngày 22/11\n"
    "I49, 51,55,57,58,60,63,64,67,\n"
    "H65,62,53,50\n"
    "G50,65,65\n"
    "F54,55,57,64,67,69\n"
    "A155\n"
    "B153,155\n"
    "E153,155\n"
    "Dầm f66-67, a-b153,b-d153"
)

PILE_CODES = [
    "I49", "I51", "I55", "I57", "I58", "I60", "I63", "I64", "I67",
    "H65", "H62", "H53", "H50",
    "G50", "G65",
    "F54", "F55", "F57", "F64", "F67", "F69",
    "A155", "B153", "B155", "E153", "E155",
]
BEAM_CODES = ["F-66-67", "A-B-153", "B-D-153"]


def _seed(session_factory):
    with session_factory() as db:
        chinh = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
        bunke = StructureZone(project_id="p1", name="Bunke", name_key="bunke")
        db.add_all([chinh, bunke])
        db.flush()
        pd2 = Segment(zone_id=chinh.id, number=2, source_code="PD2")
        bunke_segment = Segment(zone_id=bunke.id, number=1, source_code="BUNKE")
        db.add_all([pd2, bunke_segment])
        db.flush()

        # Every component owns its stage list; project-wide definitions that are
        # not attached must never become candidates.
        pile_stage_names = [
            "Đục hà bám chiều dày trung bình 10 mm",
            "Đục bê tông om vỡ dày trung bình t",
            "Tẩy gỉ cốt thép theo tỷ lệ vùng đục",
            "Vệ sinh bề mặt cọc sau khi đục",
        ]
        beam_stage_names = {
            mm: f"Đục bê tông om vỡ dày trung bình {mm} mm"
            for mm in (20, 50, 70, 100)
        }
        db.add_all(
            [
                StageDefinition(
                    project_id="p1", component_type="pile",
                    code="OTHER-PILE", name="Đục bê tông om vỡ dày trung bình 999 mm",
                    position=0,
                ),
                StageDefinition(
                    project_id="p1", component_type="beam",
                    code="OTHER-BEAM", name="Đục bê tông om vỡ dày trung bình 999 mm",
                    position=0,
                ),
            ]
        )
        db.flush()

        piles = []
        for code in PILE_CODES:
            component = StructuralComponent(
                project_id="p1", segment_id=pd2.id, type="pile",
                raw_code=code, canonical_code=code, verification="verified",
                created_by="u1",
            )
            db.add(component)
            piles.append(component)
        beams = []
        for code in BEAM_CODES:
            component = StructuralComponent(
                project_id="p1", segment_id=bunke_segment.id, type="beam",
                raw_code=code, canonical_code=code, verification="verified",
                created_by="u1",
            )
            db.add(component)
            beams.append(component)
        db.flush()

        om_vo_by_code: Dict[str, StageDefinition] = {}
        component_stage_rows: Dict[tuple[str, str], ComponentStage] = {}
        for component in piles:
            for index, name in enumerate(pile_stage_names):
                definition = StageDefinition(
                    project_id="p1", component_type="pile",
                    code=f"{component.canonical_code}-P{index}", name=name, position=index,
                )
                db.add(definition)
                db.flush()
                row = ComponentStage(
                    component_id=component.id, stage_definition_id=definition.id,
                    repair_scope_id="scope-1", created_by="u1",
                )
                db.add(row)
                component_stage_rows[(component.id, definition.id)] = row
                if "om vỡ" in name:
                    om_vo_by_code[component.canonical_code] = definition

        beam_om_vo_by_code: Dict[str, Dict[int, StageDefinition]] = {}
        for component in beams:
            beam_om_vo_by_code[component.canonical_code] = {}
            for index, (mm, name) in enumerate(beam_stage_names.items()):
                definition = StageDefinition(
                    project_id="p1", component_type="beam",
                    code=f"{component.canonical_code}-{mm}", name=name, position=index,
                )
                db.add(definition)
                db.flush()
                row = ComponentStage(
                    component_id=component.id, stage_definition_id=definition.id,
                    repair_scope_id="scope-1", created_by="u1",
                )
                db.add(row)
                component_stage_rows[(component.id, definition.id)] = row
                beam_om_vo_by_code[component.canonical_code][mm] = definition
        db.flush()

        # Recent real-world usage drives the suggested stage.
        i49 = next(component for component in piles if component.canonical_code == "I49")
        db.add(
            ProgressEvent(
                component_id=i49.id,
                component_stage_id=component_stage_rows[
                    (i49.id, om_vo_by_code["I49"].id)
                ].id,
                event_date=date(2026, 11, 21),
                status="IN_PROGRESS",
            )
        )
        f66 = next(component for component in beams if component.canonical_code == "F-66-67")
        f66_50 = beam_om_vo_by_code["F-66-67"][50]
        db.add_all(
            [
                ProgressEvent(
                    component_id=f66.id,
                    component_stage_id=component_stage_rows[(f66.id, f66_50.id)].id,
                    event_date=date(2026, 11, 20),
                    status="COMPLETED",
                    quantity=0.1,
                    unit="m3",
                ),
                ProgressEvent(
                    component_id=f66.id,
                    component_stage_id=component_stage_rows[(f66.id, f66_50.id)].id,
                    event_date=date(2026, 11, 22),
                    status="COMPLETED",
                    quantity=0.1,
                    unit="m3",
                ),
            ]
        )
        for code, mm in (("A-B-153", 70), ("B-D-153", 70)):
            component = next(item for item in beams if item.canonical_code == code)
            definition = beam_om_vo_by_code[code][mm]
            db.add(
                ProgressEvent(
                    component_id=component.id,
                    component_stage_id=component_stage_rows[(component.id, definition.id)].id,
                    event_date=date(2026, 11, 22),
                    status="COMPLETED",
                    quantity=0.1,
                    unit="m3",
                )
            )
        db.commit()
        return {
            "zone": chinh.id,
            "segment": pd2.id,
            "pile_ids": {component.id for component in piles},
            "beam_ids": {component.id for component in beams},
            "by_code": {component.canonical_code: component.id for component in piles},
            "beams": beams,
            "om_vo_by_code": {
                code: definition.id for code, definition in om_vo_by_code.items()
            },
            "pile_stage_name": "Đục bê tông om vỡ dày trung bình t",
            "beam_om_vo_by_code": {
                code: {mm: definition.id for mm, definition in mapping.items()}
                for code, mapping in beam_om_vo_by_code.items()
            },
            "f66": f66.id,
        }


def test_golden_zalo_message_parses_26_piles_3_beams_and_questions(client, session_factory):
    seeded = _seed(session_factory)
    response = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": GOLDEN_MESSAGE, "default_date": "2026-01-01"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["event_date"] == "2026-11-22"
    assert body["date_source"] == "text"
    assert any(
        "Trạng thái mặc định là Hoàn thành" in warning
        for warning in body["warnings"]
    )
    assert not any("COMPLETED" in warning for warning in body["warnings"])

    pile_ids = {
        item["component_id"]
        for line in body["lines"] if line["component_type"] == "pile"
        for item in line["items"] if item["component_id"]
    }
    beam_ids = {
        item["component_id"]
        for line in body["lines"] if line["component_type"] == "beam"
        for item in line["items"] if item["component_id"]
    }
    assert pile_ids == seeded["pile_ids"]
    assert len(pile_ids) == 26
    assert beam_ids == seeded["beam_ids"]
    assert len(beam_ids) == 3
    assert {item["status_guess"] for line in body["lines"] for item in line["items"]} == {
        "COMPLETED"
    }
    assert {line["work_text"] for line in body["lines"] if line["component_type"] == "pile"} == {
        "Cọc đục"
    }
    assert all(
        line["work_text"] == "Dầm đục"
        for line in body["lines"] if line["component_type"] == "beam"
    )

    pile_items = [
        item for line in body["lines"] if line["component_type"] == "pile"
        for item in line["items"] if item["component_id"]
    ]
    beam_items = [
        item for line in body["lines"] if line["component_type"] == "beam"
        for item in line["items"] if item["component_id"]
    ]
    assert pile_items and beam_items
    assert all(
        item["stage_definition_id"] == seeded["om_vo_by_code"][item["code"]]
        for item in pile_items
    )
    assert all(item["stage_candidates"] == [] for item in pile_items)
    assert all(item["stage_definition_id"] is not None for item in beam_items)
    assert all(len(item["stage_candidates"]) == 4 for item in beam_items)
    assert all(item["in_batch"] is False for item in pile_items + beam_items)
    assert all(
        "999 mm" not in option["name"]
        for item in pile_items + beam_items
        for option in item["stage_candidates"]
    )
    f66_item = next(item for item in beam_items if item["code"] == "F-66-67")
    ab_item = next(item for item in beam_items if item["code"] == "A-B-153")
    assert f66_item["stage_definition_id"] == seeded["beam_om_vo_by_code"]["F-66-67"][50]
    assert ab_item["stage_definition_id"] == seeded["beam_om_vo_by_code"]["A-B-153"][70]
    assert len(f66_item["earlier_events"]) == 1
    assert f66_item["earlier_events"][0]["status"] == "COMPLETED"
    assert f66_item["earlier_events"][0]["event_date"] == "2026-11-20"

    kinds = {question["kind"] for question in body["questions"]}
    assert kinds == {
        "duplicate_code",
        "completed_earlier",
        "multiple_stage",
        "outside_scope",
    }
    assert all(question["codes"] for question in body["questions"])
    assert {
        question["apply"]["action"] for question in body["questions"]
    } == {
        "dedupe",
        "correct_earlier_to_in_progress",
        "set_stage",
        "skip_codes",
    }
    duplicate = next(q for q in body["questions"] if q["kind"] == "duplicate_code")
    assert "G65" in duplicate["message_vi"]
    assert duplicate["codes"] == ["G65"]
    assert duplicate["apply"] == {"action": "dedupe", "codes": ["G65"]}
    assert {option["value"] for option in duplicate["options"]} == {
        "dedupe",
        "replace_code",
    }

    completed = next(q for q in body["questions"] if q["kind"] == "completed_earlier")
    assert "F-66-67" in completed["message_vi"]
    assert "20/11/2026" in completed["message_vi"]
    assert "Hoàn thành" in completed["message_vi"]
    assert "COMPLETED" not in completed["message_vi"]
    assert completed["codes"] == ["F-66-67"]
    assert completed["apply"]["action"] == "correct_earlier_to_in_progress"
    assert len(completed["apply"]["event_ids"]) == 1
    assert {option["value"] for option in completed["options"]} == {
        "add_completed",
        "previous_was_in_progress",
        "skip",
    }

    stage_question = next(
        q for q in body["questions"]
        if q["kind"] == "multiple_stage" and "F-66-67" in q["message_vi"]
    )
    assert len(stage_question["options"]) == 4
    assert stage_question["apply"]["action"] == "set_stage"
    assert stage_question["apply"]["stage_definition_id"] == seeded[
        "beam_om_vo_by_code"
    ]["F-66-67"][50]
    assert stage_question["options"][0]["value"] == seeded["beam_om_vo_by_code"][
        "F-66-67"
    ][50]
    assert stage_question["codes"] == ["F-66-67"]
    assert {option["label_vi"] for option in stage_question["options"]} == {
        "Đục bê tông om vỡ dày trung bình 20 mm",
        "Đục bê tông om vỡ dày trung bình 50 mm",
        "Đục bê tông om vỡ dày trung bình 70 mm",
        "Đục bê tông om vỡ dày trung bình 100 mm",
    }

    outside = next(q for q in body["questions"] if q["kind"] == "outside_scope")
    assert "Bunke" in outside["message_vi"]
    assert outside["apply"]["action"] == "skip_codes"
    assert {option["value"] for option in outside["options"]} == {"include", "skip"}


def test_parser_does_not_write_to_database(client, session_factory):
    seeded = _seed(session_factory)
    with session_factory() as db:
        from sqlalchemy import func, select

        before = db.scalar(select(func.count()).select_from(ProgressEvent))

    response = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": GOLDEN_MESSAGE},
    )
    assert response.status_code == 200, response.text

    with session_factory() as db:
        from sqlalchemy import func, select

        after = db.scalar(select(func.count()).select_from(ProgressEvent))
    assert after == before
    assert seeded["pile_ids"]


def test_parser_is_project_scoped_and_matches_aliases(client, session_factory):
    seeded = _seed(session_factory)
    with session_factory() as db:
        foreign_zone = StructureZone(project_id="p2", name="Khác", name_key="khac")
        db.add(foreign_zone)
        db.flush()
        foreign_segment = Segment(zone_id=foreign_zone.id, number=1, source_code="P1")
        db.add(foreign_segment)
        db.flush()
        foreign = StructuralComponent(
            project_id="p2", segment_id=foreign_segment.id, type="pile",
            raw_code="I49", canonical_code="I49", verification="verified",
            created_by="u1",
        )
        db.add(foreign)
        db.flush()
        db.add(
            ComponentAlias(
                component_id=seeded["by_code"]["H65"],
                project_id="p1",
                segment_id=seeded["segment"],
                type="pile",
                alias="HH65",
            )
        )
        db.commit()
        foreign_id = foreign.id

    response = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": "Cọc đục ngày 22/11\nI49\nhh65"},
    )
    assert response.status_code == 200, response.text
    items = [item for line in response.json()["lines"] for item in line["items"]]
    by_code = {item["code"]: item["component_id"] for item in items}
    assert by_code["I49"] != foreign_id
    assert by_code["H65"] == seeded["by_code"]["H65"]
    assert foreign_id not in by_code.values()


def test_direct_canonical_beam_codes_are_accepted(client, session_factory):
    seeded = _seed(session_factory)
    response = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": "Dầm đục ngày 22/11\nDầm F-66-67, A-B-153, B-D-153"},
    )
    assert response.status_code == 200, response.text
    items = [item for line in response.json()["lines"] for item in line["items"]]
    assert {item["component_id"] for item in items} == seeded["beam_ids"]


def test_parser_ignores_voided_completed_when_building_questions(client, session_factory):
    seeded = _seed(session_factory)
    with session_factory() as db:
        from sqlalchemy import select

        h65 = db.scalar(
            select(StructuralComponent).where(
                StructuralComponent.project_id == "p1",
                StructuralComponent.canonical_code == "H65",
            )
        )
        stage = db.scalar(
            select(ComponentStage).where(ComponentStage.component_id == h65.id)
        )
        from datetime import datetime, timezone

        db.add(
            ProgressEvent(
                component_id=h65.id,
                component_stage_id=stage.id,
                event_date=date(2026, 11, 21),
                status="COMPLETED",
                voided_at=datetime.now(timezone.utc),
                void_reason="Nhập sai",
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": "Cọc đục ngày 22/11\nH65"},
    )
    assert response.status_code == 200, response.text
    kinds = {question["kind"] for question in response.json()["questions"]}
    assert "completed_earlier" not in kinds
    assert seeded["by_code"]["H65"]




def test_batch_member_beam_is_not_flagged_but_others_are(client, session_factory):
    seeded = _seed(session_factory)
    with session_factory() as db:
        from sqlalchemy import select

        ab153 = db.scalar(
            select(StructuralComponent).where(
                StructuralComponent.project_id == "p1",
                StructuralComponent.canonical_code == "A-B-153",
            )
        )
        batch = ConstructionBatch(
            project_id="p1",
            name="Bunke đợt PD2",
            created_by="u1",
        )
        db.add(batch)
        db.flush()
        db.add(
            ConstructionBatchComponent(
                batch_id=batch.id,
                component_id=ab153.id,
                added_by="u1",
            )
        )
        db.commit()
        batch_id = batch.id

    response = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": GOLDEN_MESSAGE, "batch_id": batch_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["batch_id"] == batch_id
    outside = next(q for q in body["questions"] if q["kind"] == "outside_scope")
    assert "A-B-153" not in outside["message_vi"]
    assert "F-66-67" in outside["message_vi"]
    assert "B-D-153" in outside["message_vi"]
    items = [item for line in body["lines"] for item in line["items"]]
    batched = next(item for item in items if item["code"] == "A-B-153")
    others = [item for item in items if item["code"] in {"F-66-67", "B-D-153"}]
    assert batched["in_batch"] is True
    assert all(item["in_batch"] is False for item in others)
    assert seeded["beam_ids"]


def test_duplicate_stage_names_get_unique_option_labels(client, session_factory):
    with session_factory() as db:
        zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
        db.add(zone)
        db.flush()
        segment = Segment(zone_id=zone.id, number=2, source_code="PD2")
        db.add(segment)
        db.flush()
        component = StructuralComponent(
            project_id="p1", segment_id=segment.id, type="pile",
            raw_code="I69", canonical_code="I69", verification="verified",
            created_by="u1",
        )
        db.add(component)
        db.flush()
        for index in range(2):
            definition = StageDefinition(
                project_id="p1", component_type="pile",
                code=f"DUP-{index}", name="Đục bê tông om vỡ dày trung bình t",
                position=index,
            )
            db.add(definition)
            db.flush()
            db.add(
                ComponentStage(
                    component_id=component.id,
                    stage_definition_id=definition.id,
                    repair_scope_id=f"scope-{index}",
                    created_by="u1",
                )
            )
        db.commit()

    body = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": "Cọc đục ngày 22/11\nI69"},
    ).json()
    item = next(item for line in body["lines"] for item in line["items"])
    assert item["stage_candidates"]
    labels = [candidate["name"] for candidate in item["stage_candidates"]]
    assert len(labels) == len(set(labels))


def test_stage_labels_and_questions_show_component_t(client, session_factory):
    seeded = _seed(session_factory)
    with session_factory() as db:
        from sqlalchemy import select

        component = db.scalar(
            select(StructuralComponent).where(
                StructuralComponent.project_id == "p1",
                StructuralComponent.canonical_code == "I49",
            )
        )
        db.add(
            ComponentDesignParameter(
                project_id="p1",
                component_id=component.id,
                name="t_cm",
                value=3.0,
                unit="cm",
                source_drawing="TK-19",
                source_page=23,
                source_row=14,
                created_by="u1",
            )
        )
        definition = StageDefinition(
            project_id="p1",
            component_type="pile",
            code="DUP-T",
            name="Đục bê tông om vỡ dày trung bình t",
            position=9,
        )
        db.add(definition)
        db.flush()
        db.add(
            ComponentStage(
                component_id=component.id,
                stage_definition_id=definition.id,
                repair_scope_id="scope-2",
                created_by="u1",
            )
        )
        db.commit()

    body = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": "Cọc đục ngày 22/11\nI49"},
    ).json()
    item = next(item for line in body["lines"] for item in line["items"])
    labels = [candidate["name"] for candidate in item["stage_candidates"]]
    assert len(labels) == 2
    assert all("t = 3 cm" in label for label in labels)
    question = next(q for q in body["questions"] if q["kind"] == "multiple_stage")
    assert all("t = 3 cm" in option["label_vi"] for option in question["options"])
    assert seeded["by_code"]["I49"] == item["component_id"]


def test_same_kind_and_options_are_grouped_for_apply_all(client, session_factory):
    with session_factory() as db:
        zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
        db.add(zone)
        db.flush()
        segment = Segment(zone_id=zone.id, number=2, source_code="PD2")
        db.add(segment)
        db.flush()
        definitions = []
        for index, name in enumerate(
            (
                "Đục bê tông om vỡ dày trung bình t",
                "Đục bê tông om vỡ đáy sườn t",
            )
        ):
            definition = StageDefinition(
                project_id="p1",
                component_type="pile",
                code=f"DUP-{index}",
                name=name,
                position=index,
            )
            db.add(definition)
            definitions.append(definition)
        db.flush()
        for code in ("I69", "I70"):
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
            db.flush()
            for definition in definitions:
                db.add(
                    ComponentStage(
                        component_id=component.id,
                        stage_definition_id=definition.id,
                        repair_scope_id="scope-1",
                        created_by="u1",
                    )
                )
        db.commit()

    body = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": "Cọc đục ngày 22/11\nI69,70"},
    ).json()
    stage_questions = [q for q in body["questions"] if q["kind"] == "multiple_stage"]
    assert len(stage_questions) == 1
    assert stage_questions[0]["codes"] == ["I69", "I70"]
    assert stage_questions[0]["target_codes"] == ["I69", "I70"]
    assert len(stage_questions[0]["options"]) == 2
    assert {item["code"] for line in body["lines"] for item in line["items"]} == {
        "I69",
        "I70",
    }


def test_unknown_code_and_missing_status_questions(client, session_factory):
    _seed(session_factory)
    response = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": "Cọc đang đục ngày 22/11\nI49, Z999"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unknown_codes"] == ["Z999"]
    kinds = {question["kind"] for question in body["questions"]}
    assert "unknown_code" in kinds
    assert "status_confirm" in kinds
    statuses = {item["status_guess"] for line in body["lines"] for item in line["items"]}
    assert statuses == {"IN_PROGRESS"}


def test_missing_date_uses_default_and_warns_without_date(session_factory):
    _seed(session_factory)
    with session_factory() as db:
        body = progress_parse(db, "p1", "Cọc đục\nI49", date(2025, 3, 4))
        assert str(body.event_date) == "2025-03-04"
        assert body.date_source == "default_date"

        no_date = progress_parse(db, "p1", "Cọc đục\nI49", None)
        assert no_date.event_date is None
        assert no_date.date_source is None
        assert any("Chưa xác định được ngày" in warning for warning in no_date.warnings)


def test_future_date_returns_question_and_vietnamese_warning(client, session_factory):
    _seed(session_factory)
    tomorrow = date.today() + timedelta(days=1)
    body = client.post(
        "/api/v1/projects/p1/ai/progress-parse",
        json={"text": f"Cọc đục ngày {tomorrow:%d/%m/%Y}\nI49"},
    ).json()
    question = next(q for q in body["questions"] if q["kind"] == "future_date")
    assert [option["value"] for option in question["options"]] == ["today", "keep"]
    assert [option["label_vi"] for option in question["options"]] == [
        "Dùng ngày hôm nay",
        "Giữ ngày và sửa tay",
    ]
    assert question["apply"]["today"] == date.today().isoformat()
    assert any("sau ngày hôm nay" in warning for warning in body["warnings"])
    assert "COMPLETED" not in question["message_vi"]
