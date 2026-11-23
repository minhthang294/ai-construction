"""Pending acceptance queue and PYC prefill from completed progress."""

from datetime import date, datetime, timezone

from app.acceptance.models import AcceptanceRecord, AcceptanceRequest, ComponentAcceptanceLink
from app.core.component_models import (
    ComponentDesignParameter,
    ComponentStage,
    ComponentWorkLink,
    ConstructionBatch,
    ConstructionBatchComponent,
    ProgressEvent,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.models import WorkItem


def _seed(session_factory):
    with session_factory() as db:
        zone = StructureZone(project_id="p1", name="Cầu chính", name_key="cau chinh")
        db.add(zone)
        db.flush()
        segment = Segment(zone_id=zone.id, number=2, source_code="PD2")
        db.add(segment)
        db.flush()
        definition = StageDefinition(
            project_id="p1",
            component_type="pile",
            code="DUC",
            name="Đục bê tông om vỡ dày trung bình t",
            position=0,
        )
        db.add(definition)
        db.flush()
        components = []
        stages = []
        for code in ("F67", "F68", "F69", "F70", "F71"):
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
            scope = RepairScope(
                component_id=component.id,
                kind="DESIGN_SCOPE",
                verification="VERIFIED",
                revision=1,
            )
            db.add(scope)
            db.flush()
            stage = ComponentStage(
                component_id=component.id,
                stage_definition_id=definition.id,
                repair_scope_id=scope.id,
                created_by="u1",
            )
            db.add(stage)
            db.flush()
            components.append(component)
            stages.append(stage)
        db.add_all(
            [
                ComponentDesignParameter(
                    project_id="p1", component_id=components[0].id, name="t_cm",
                    value=3, unit="cm", source_drawing="TK-19", source_page=23,
                    source_row=14, created_by="u1",
                ),
                ComponentDesignParameter(
                    project_id="p1", component_id=components[1].id, name="t_cm",
                    value=5, unit="cm", source_drawing="TK-19", source_page=23,
                    source_row=20, created_by="u1",
                ),
                ComponentDesignParameter(
                    project_id="p1", component_id=components[4].id, name="t_cm",
                    value=3, unit="cm", source_drawing="TK-19", source_page=24,
                    source_row=5, created_by="u1",
                ),
            ]
        )
        db.add_all(
            [
                ProgressEvent(
                    component_id=components[0].id, component_stage_id=stages[0].id,
                    event_date=date(2026, 11, 21), status="COMPLETED",
                ),
                ProgressEvent(
                    component_id=components[1].id, component_stage_id=stages[1].id,
                    event_date=date(2026, 11, 21), status="COMPLETED",
                ),
                ProgressEvent(
                    component_id=components[2].id, component_stage_id=stages[2].id,
                    event_date=date(2026, 11, 22), status="COMPLETED",
                    voided_at=datetime.now(timezone.utc), void_reason="Nhập trùng",
                ),
                ProgressEvent(
                    component_id=components[3].id, component_stage_id=stages[3].id,
                    event_date=date(2026, 11, 22), status="IN_PROGRESS",
                ),
                ProgressEvent(
                    component_id=components[4].id, component_stage_id=stages[4].id,
                    event_date=date(2026, 11, 22), status="COMPLETED",
                ),
            ]
        )
        # F68 already has a human-confirmed BBNT for this exact stage.
        request = AcceptanceRequest(
            project_id="p1", number="PYC-OLD", status="draft",
        )
        db.add(request)
        db.flush()
        record = AcceptanceRecord(
            project_id="p1", request_id=request.id, number="BBNT-OLD",
            revision=1, status="confirmed", result="approved",
        )
        db.add(record)
        db.flush()
        db.add(
            ComponentAcceptanceLink(
                project_id="p1", component_id=components[1].id,
                stage_id=stages[1].id, scope_id="scope-1",
                record_id=record.id, created_by="u1",
            )
        )
        batch = ConstructionBatch(
            project_id="p1", name="Đợt PD2", created_by="u1",
        )
        db.add(batch)
        db.flush()
        db.add(
            ConstructionBatchComponent(
                batch_id=batch.id, component_id=components[0].id, added_by="u1",
            )
        )
        work_item = WorkItem(
            project_id="p1",
            code="W-DUC",
            name="Đục bê tông om vỡ",
            status="planned",
        )
        db.add(work_item)
        db.flush()
        for component in (components[0], components[4]):
            db.add(
                ComponentWorkLink(
                    component_id=component.id,
                    source_hash="c" * 64,
                    dm_row=1,
                    seed_sheet="LIEN_KET_CONG_VIEC",
                    seed_row=1,
                    work="Đục bê tông om vỡ",
                    raw_location="Cầu chính - PD2",
                )
            )
        db.commit()
        return {
            "component_ids": [component.id for component in components],
            "stage_ids": [stage.id for stage in stages],
            "definition_id": definition.id,
            "batch_id": batch.id,
            "work_item_id": work_item.id,
        }


def test_pending_queue_ignores_voided_and_excludes_confirmed(client, session_factory):
    seeded = _seed(session_factory)

    body = client.get("/api/v1/projects/p1/acceptance/pending").json()
    assert body["total_components"] == 2
    group = body["groups"][0]
    assert group["stage_name"].endswith("t = 3 cm")
    assert group["zone"] == "Cầu chính"
    assert group["segment"] == 2
    assert group["event_dates"] == ["2026-11-21", "2026-11-22"]
    assert [item["code"] for item in group["components"]] == ["F67", "F71"]
    assert group["components"][0]["component_id"] == seeded["component_ids"][0]


def test_pending_queue_filters_batch_and_stage(client, session_factory):
    seeded = _seed(session_factory)

    batch = client.get(
        "/api/v1/projects/p1/acceptance/pending",
        params={"batch_id": seeded["batch_id"]},
    ).json()
    assert batch["total_components"] == 1
    assert [item["code"] for item in batch["groups"][0]["components"]] == ["F67"]

    other_stage = client.get(
        "/api/v1/projects/p1/acceptance/pending",
        params={"stage_definition_id": "missing-definition"},
    ).json()
    assert other_stage["total_components"] == 0


def test_pending_queue_is_project_scoped(client, session_factory):
    _seed(session_factory)
    body = client.get("/api/v1/projects/p2/acceptance/pending").json()
    assert body["total_components"] == 0
    assert body["groups"] == []


def test_create_request_from_components_prefills_draft_and_links(client, session_factory):
    seeded = _seed(session_factory)
    response = client.post(
        "/api/v1/projects/p1/acceptance/requests/from-components",
        json={
            "component_ids": [seeded["component_ids"][0], seeded["component_ids"][4]],
            "event_date": "2026-11-20",
        },
    )
    assert response.status_code == 201, response.text
    request = response.json()
    assert request["status"] == "draft"
    assert request["work_item_id"] == seeded["work_item_id"]
    assert request["request_date"] == "2026-11-23"  # next working day after Friday
    assert "Cầu chính" in request["location"]
    assert "F67" in request["location"] and "F71" in request["location"]
    assert "t = 3 cm" in request["subject"]
    assert "chưa có kết luận nghiệm thu" in request["content"]

    links = client.get(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/component-links"
    ).json()
    assert {item["component_id"] for item in links} == {
        seeded["component_ids"][0],
        seeded["component_ids"][4],
    }
    assert all(item["stage_id"] in seeded["stage_ids"] for item in links)

    with session_factory() as db:
        from sqlalchemy import func, select

        assert db.scalar(select(func.count()).select_from(AcceptanceRecord)) == 1
        created_links = db.scalars(
            select(ComponentAcceptanceLink).where(
                ComponentAcceptanceLink.request_id == request["id"]
            )
        ).all()
        assert len(created_links) == 2
        assert all(link.record_id is None for link in created_links)

    still_pending = client.get("/api/v1/projects/p1/acceptance/pending").json()
    assert still_pending["total_components"] == 2  # PYC draft is not acceptance


def test_create_request_from_components_rejects_non_pending(client, session_factory):
    seeded = _seed(session_factory)
    response = client.post(
        "/api/v1/projects/p1/acceptance/requests/from-components",
        json={"component_ids": [seeded["component_ids"][2]]},  # voided event
    )
    assert response.status_code == 409
    assert response.json()["code"] == "components_not_pending"


def test_pending_exposes_stage_display_name_for_missing_t(client, session_factory):
    seeded = _seed(session_factory)
    other = client.get(
        "/api/v1/projects/p1/acceptance/pending",
        params={"batch_id": seeded["batch_id"]},
    ).json()
    assert other["groups"][0]["stage_name"].endswith("t = 3 cm")
