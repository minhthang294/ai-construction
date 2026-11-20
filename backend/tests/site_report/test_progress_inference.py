"""Read-time DAP progress inference: exact scope, explicit status, retraction."""

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.component_models import (
    ComponentStage,
    ProgressEvent,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.site.models import Base  # noqa: F401 - registers shared metadata
from app.site.progress_inference import apply_inferred_progress


def test_actual_grout_can_infer_multiple_prerequisites_in_the_same_scope():
    stages = [
        {"id": "chip", "name": "Đục bê tông dày TB 30 mm", "status": "NOT_STARTED"},
        {"id": "form", "name": "Ván khuôn", "status": "NOT_STARTED"},
        {"id": "grout", "name": "Vữa không co ngót tính năng cao", "status": "COMPLETED",
         "latest_event_at": datetime(2026, 11, 20, tzinfo=timezone.utc)},
    ]
    for stage in stages:
        stage.update(code=f"DAP-{stage['id']}", repair_scope_id="scope")
    apply_inferred_progress("beam", stages)
    assert [stage["inferred_from_stage_id"] for stage in stages] == ["grout", "grout", None]


def _seed(Session, events=()):
    with Session() as db:
        db.add(StructureZone(id="z1", project_id="p1", name="Cầu chính", name_key="cầu chính"))
        db.flush()
        db.add(Segment(id="seg1", zone_id="z1", number=1, source_code="PD1"))
        db.flush()
        db.add(
            StructuralComponent(
                id="c1",
                project_id="p1",
                segment_id="seg1",
                type="pile",
                raw_code="I36",
                canonical_code="I36",
                verification="VERIFIED",
                record_origin="SEED_IMPORT",
                created_by="test-user",
            )
        )
        db.add_all(
            [
                RepairScope(
                    id="sc-design",
                    component_id="c1",
                    kind="DESIGN_SCOPE",
                    verification="VERIFIED",
                ),
                RepairScope(
                    id="sc-additional",
                    component_id="c1",
                    kind="ADDITIONAL_SCOPE",
                    verification="VERIFIED",
                ),
            ]
        )
        # Positions are deliberately reversed: inference must use the reviewed
        # DAP name/kind graph, not the stored display order.
        db.add_all(
            [
                StageDefinition(
                    id="def-chip",
                    project_id="p1",
                    component_type="pile",
                    code="DAP-PILE-CHIP",
                    name="Đục bê tông om vỡ dày trung bình t",
                    position=9000,
                ),
                StageDefinition(
                    id="def-rust",
                    project_id="p1",
                    component_type="pile",
                    code="DAP-PILE-RUST",
                    name="Tẩy gỉ cốt thép theo tỷ lệ vùng đục",
                    position=1,
                ),
                StageDefinition(
                    id="def-unknown",
                    project_id="p1",
                    component_type="pile",
                    code="DAP-PILE-UNKNOWN",
                    name="Bước chưa đối chiếu",
                    position=2,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                ComponentStage(
                    id="st-chip-design",
                    component_id="c1",
                    stage_definition_id="def-chip",
                    repair_scope_id="sc-design",
                    created_by="test-user",
                ),
                ComponentStage(
                    id="st-rust-design",
                    component_id="c1",
                    stage_definition_id="def-rust",
                    repair_scope_id="sc-design",
                    created_by="test-user",
                ),
                ComponentStage(
                    id="st-chip-additional",
                    component_id="c1",
                    stage_definition_id="def-chip",
                    repair_scope_id="sc-additional",
                    created_by="test-user",
                ),
                ComponentStage(
                    id="st-rust-additional",
                    component_id="c1",
                    stage_definition_id="def-rust",
                    repair_scope_id="sc-additional",
                    created_by="test-user",
                ),
                ComponentStage(
                    id="st-unknown",
                    component_id="c1",
                    stage_definition_id="def-unknown",
                    repair_scope_id="sc-design",
                    created_by="test-user",
                ),
            ]
        )
        for event in events:
            db.add(
                ProgressEvent(
                    id=event["id"],
                    component_id="c1",
                    component_stage_id=event["stage_id"],
                    event_date=event.get("event_date", date(2026, 11, 18)),
                    status=event["status"],
                    evidence_refs="[]",
                    created_by="test-user",
                    created_at=event["created_at"],
                )
            )
        db.commit()


def _row(client):
    response = client.get("/api/v1/projects/p1/progress")
    assert response.status_code == 200, response.text
    return response.json()[0]


def _event(stage_id, status, event_id, hour):
    return {
        "id": event_id,
        "stage_id": stage_id,
        "status": status,
        "created_at": datetime(2026, 11, 18, hour, tzinfo=timezone.utc),
    }


def test_inference_uses_same_scope_and_reviewed_names_only(client, db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    _seed(Session, [_event("st-rust-design", "COMPLETED", "ev-rust", 9)])

    stages = {stage["id"]: stage for stage in _row(client)["stages"]}
    assert stages["st-chip-design"]["status"] == "COMPLETED"
    assert stages["st-chip-design"]["inferred_from_stage_id"] == "st-rust-design"
    assert stages["st-chip-design"]["inference_conflict"] is False
    assert stages["st-chip-design"]["latest_event_at"] is None
    # A completed source in DESIGN_SCOPE must not infer the ADDITIONAL_SCOPE copy.
    assert stages["st-chip-additional"]["status"] == "NOT_STARTED"
    assert stages["st-chip-additional"]["inferred_from_stage_id"] is None
    # Unknown DAP names stay untouched even when a later phase is completed.
    assert stages["st-unknown"]["status"] == "NOT_STARTED"
    assert stages["st-unknown"]["inferred_from_stage_id"] is None

    with Session() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 1

    # Reading the projection (and the journal preview) must not create events
    # for the inferred stage.
    preview = client.get("/api/v1/projects/p1/journals/2026-11-18/preview")
    assert preview.status_code == 200, preview.text
    stage_ids = [item["stage_id"] for item in preview.json()["construction_events"]]
    assert stage_ids == ["st-rust-design"]
    with Session() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 1


def test_explicit_prior_status_wins_and_marks_conflict(
    client, db_engine
):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    _seed(
        Session,
        [
            _event("st-chip-design", "IN_PROGRESS", "ev-chip", 8),
            _event("st-rust-design", "COMPLETED", "ev-rust", 9),
        ],
    )

    row = _row(client)
    stages = {stage["id"]: stage for stage in row["stages"]}
    assert stages["st-chip-design"]["status"] == "IN_PROGRESS"
    assert stages["st-chip-design"]["inference_conflict"] is True
    assert stages["st-chip-design"]["inferred_from_stage_id"] == "st-rust-design"
    assert row["construction_event"]["stage_id"] == "st-rust-design"

    with Session() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 2

    preview = client.get("/api/v1/projects/p1/journals/2026-11-18/preview")
    assert preview.status_code == 200, preview.text
    stage_ids = [item["stage_id"] for item in preview.json()["construction_events"]]
    assert stage_ids == ["st-chip-design", "st-rust-design"]
    with Session() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 2


def test_inference_is_retracted_when_successor_gets_a_later_status(client, db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    _seed(Session, [_event("st-rust-design", "COMPLETED", "ev-rust", 9)])

    stages = {stage["id"]: stage for stage in _row(client)["stages"]}
    assert stages["st-chip-design"]["status"] == "COMPLETED"
    assert stages["st-chip-design"]["inferred_from_stage_id"] == "st-rust-design"

    with Session() as db:
        db.add(
            ProgressEvent(
                id="ev-rust-retract",
                component_id="c1",
                component_stage_id="st-rust-design",
                event_date=date(2026, 11, 19),
                status="IN_PROGRESS",
                evidence_refs="[]",
                created_by="test-user",
                created_at=datetime(2026, 11, 19, 9, tzinfo=timezone.utc),
            )
        )
        db.commit()

    stages = {stage["id"]: stage for stage in _row(client)["stages"]}
    assert stages["st-chip-design"]["status"] == "NOT_STARTED"
    assert stages["st-chip-design"]["inferred_from_stage_id"] is None
    assert stages["st-chip-design"]["inference_conflict"] is False
