"""Golden tests for the deterministic Zalo progress parser (read-only)."""

from datetime import date

from app.core.component_models import (
    ComponentAlias,
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

        pile_stage = StageDefinition(
            project_id="p1", component_type="pile", code="DUC-BT",
            name="Đục bê tông", position=0,
        )
        beam_stages = [
            StageDefinition(
                project_id="p1", component_type="beam", code=code, name=name, position=index
            )
            for index, (code, name) in enumerate(
                [
                    ("DUC-SUON", "Đục sườn"),
                    ("DUC-DAY", "Đục đáy"),
                    ("DUC-OM", "Đục om vỡ"),
                ]
            )
        ]
        db.add_all([pile_stage, *beam_stages])
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

        pile_stage_rows = []
        for component in piles:
            row = ComponentStage(
                component_id=component.id, stage_definition_id=pile_stage.id,
                repair_scope_id="scope-1", created_by="u1",
            )
            db.add(row)
            pile_stage_rows.append(row)
        beam_stage_rows = []
        for component in beams:
            rows = []
            for definition in beam_stages:
                row = ComponentStage(
                    component_id=component.id, stage_definition_id=definition.id,
                    repair_scope_id="scope-1", created_by="u1",
                )
                db.add(row)
                rows.append(row)
            beam_stage_rows.append(rows)
        db.flush()

        # A previous COMPLETED for F-66-67 must raise the "already completed" question.
        db.add(
            ProgressEvent(
                component_id=beams[0].id,
                component_stage_id=beam_stage_rows[0][0].id,
                event_date=date(2026, 11, 20),
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
            "pile_stage": pile_stage.id,
            "beam_stages": [definition.id for definition in beam_stages],
            "f66": beams[0].id,
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

    kinds = {question["kind"] for question in body["questions"]}
    assert kinds == {
        "duplicate_code",
        "completed_earlier",
        "multiple_stage",
        "outside_scope",
    }
    duplicate = next(q for q in body["questions"] if q["kind"] == "duplicate_code")
    assert "G65" in duplicate["message_vi"]
    assert {option["value"] for option in duplicate["options"]} == {
        "dedupe",
        "replace_code",
    }

    completed = next(q for q in body["questions"] if q["kind"] == "completed_earlier")
    assert "F-66-67" in completed["message_vi"]
    assert "20/11/2026" in completed["message_vi"]
    assert {option["value"] for option in completed["options"]} == {
        "add_completed",
        "previous_was_in_progress",
        "skip",
    }

    stage_question = next(
        q for q in body["questions"]
        if q["kind"] == "multiple_stage" and "F-66-67" in q["message_vi"]
    )
    assert len(stage_question["options"]) == 3
    assert {option["label_vi"] for option in stage_question["options"]} == {
        "Đục sườn", "Đục đáy", "Đục om vỡ",
    }

    outside = next(q for q in body["questions"] if q["kind"] == "outside_scope")
    assert "Bunke" in outside["message_vi"]
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
    assert seeded["beam_ids"]


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
