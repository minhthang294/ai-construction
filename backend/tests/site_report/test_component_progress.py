"""Component progress, exact bulk review and reviewed journal preview."""

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.acceptance.models import (
    AcceptanceRecord,
    AcceptanceRequest,
    ComponentAcceptanceLink,
)
from app.core.component_models import (
    ComponentAlias,
    ComponentStage,
    DesignGroup,
    ProgressEvent,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.models import AuditLog
from app.site.models import SitePhoto, SiteProgressBulkBatch
from app.site.schemas import LOCAL_TZ


def _bulk(**overrides):
    payload = {
        "stage_definition_id": "sd1",
        "component_ids": ["c1"],
        "event_date": "2026-11-18",
        "status": "COMPLETED",
        "quantity": 1.5,
        "unit": "m3",
        "note": "Đã kiểm tra hiện trường",
        "evidence_refs": [],
    }
    payload.update(overrides)
    return payload


def _commit(**overrides):
    payload = {
        **_bulk(),
        "reviewed": True,
        "idempotency_key": "bulk-1",
    }
    payload.update(overrides)
    return payload


def _daily_line(**overrides):
    line = {
        "stage_definition_id": "sd1",
        "component_ids": ["c1"],
        "status": "COMPLETED",
        "group_quantity": 12.5,
        "group_unit": "m3",
    }
    line.update(overrides)
    return line


def _daily(**overrides):
    payload = {
        "event_date": "2026-11-18",
        "lines": [
            _daily_line(),
            _daily_line(
                stage_definition_id="sd2",
                component_ids=["c2"],
                status="IN_PROGRESS",
                group_quantity=0.0,
                group_unit="m3",
            ),
        ],
    }
    payload.update(overrides)
    return payload


def _daily_commit(**overrides):
    payload = {
        **_daily(),
        "reviewed": True,
        "idempotency_key": "daily-1",
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def seeded(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    with Session() as db:
        zone = StructureZone(
            id="z1", project_id="p1", name="Cầu chính", name_key="cầu chính"
        )
        other_zone = StructureZone(
            id="z2", project_id="other", name="Cầu dẫn", name_key="cầu dẫn"
        )
        db.add_all([zone, other_zone])
        db.flush()
        segment = Segment(id="s1", zone_id="z1", number=1, source_code="PD1")
        other_segment = Segment(id="s2", zone_id="z2", number=2, source_code="PD2")
        db.add_all([segment, other_segment])
        group = DesignGroup(
            id="g1",
            project_id="p1",
            group_type="PILE_REPAIR_CLASS",
            name="Nhóm 2",
            drawing="TK-02",
            source="Bản vẽ TK-02",
        )
        db.add(group)
        db.flush()
        components = [
            StructuralComponent(
                id="c1",
                project_id="p1",
                segment_id="s1",
                design_group_id="g1",
                type="pile",
                raw_code="I36",
                canonical_code="I36",
                verification="VERIFIED",
                record_origin="SEED_IMPORT",
                created_by="test-user",
            ),
            StructuralComponent(
                id="c2",
                project_id="p1",
                segment_id="s1",
                type="beam",
                raw_code="I40-42",
                canonical_code="I-40-42",
                verification="NEEDS_REVIEW",
                record_origin="MANUAL_ENTRY",
                created_by="test-user",
            ),
            StructuralComponent(
                id="c-other",
                project_id="other",
                segment_id="s2",
                type="pile",
                raw_code="X1",
                canonical_code="X1",
                verification="VERIFIED",
                record_origin="SEED_IMPORT",
                created_by="test-user",
            ),
        ]
        db.add_all(components)
        db.add_all(
            [
                RepairScope(id="sc1", component_id="c1", kind="DESIGN_SCOPE", verification="VERIFIED"),
                RepairScope(
                    id="sc2",
                    component_id="c2",
                    kind="ADDITIONAL_SCOPE",
                    verification="NEEDS_REVIEW",
                ),
                StageDefinition(
                    id="sd1",
                    project_id="p1",
                    component_type="pile",
                    code="PILE-REPAIR",
                    name="Sửa chữa cọc",
                    position=1,
                ),
                StageDefinition(
                    id="sd2",
                    project_id="p1",
                    component_type="beam",
                    code="BEAM-REPAIR",
                    name="Sửa chữa dầm",
                    position=2,
                ),
                ComponentAlias(
                    id="a1",
                    component_id="c1",
                    project_id="p1",
                    segment_id="s1",
                    type="pile",
                    alias="I-36",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                ComponentStage(
                    id="st1",
                    component_id="c1",
                    stage_definition_id="sd1",
                    repair_scope_id="sc1",
                    created_by="test-user",
                ),
                ComponentStage(
                    id="st2",
                    component_id="c2",
                    stage_definition_id="sd2",
                    repair_scope_id="sc2",
                    created_by="test-user",
                ),
            ]
        )
        db.commit()
    return Session


def test_design_quantities_only_return_selected_project_stages(client, seeded):
    quantity = {
        "quantity": 0.988,
        "unit": "m²",
        "scope": "COMPONENT",
        "scope_label": None,
        "drawing": "TK-86",
        "page": "92",
        "note": None,
    }
    with seeded() as db:
        db.get(ComponentStage, "st1").design_quantity = quantity
        db.add(RepairScope(id="sc-other", component_id="c-other", kind="DESIGN_SCOPE", verification="VERIFIED"))
        db.add(StageDefinition(id="sd-other", project_id="other", component_type="pile",
                               code="OTHER", name="Ngoài công trình"))
        db.flush()
        db.add(ComponentStage(id="st-other", component_id="c-other", stage_definition_id="sd-other",
                              repair_scope_id="sc-other", created_by="test-user",
                              design_quantity={**quantity, "quantity": 99}))
        db.commit()

    path = "/api/v1/projects/p1/progress/design-quantities"
    response = client.post(path, json={"component_ids": ["c1", "c2", "c-other"]})
    assert response.status_code == 200, response.text
    assert response.json() == {"st1": quantity}
    assert client.post(path, json={"component_ids": ["c1", " c1 "]}).status_code == 422
    rows = client.get("/api/v1/projects/p1/progress").json()
    assert all("design_quantity" not in stage for row in rows for stage in row["stages"])


def test_progress_view_keeps_statuses_independent_and_filters_exactly(client, seeded):
    response = client.get("/api/v1/projects/p1/progress")
    assert response.status_code == 200, response.text
    rows = {row["canonical_code"]: row for row in response.json()}
    assert set(rows) == {"I36", "I-40-42"}
    assert rows["I36"]["construction_status"] == "NOT_STARTED"
    assert rows["I36"]["acceptance_status"] == "NOT_LINKED"
    assert rows["I36"]["acceptance_count"] == 0
    assert rows["I36"]["design_group"] == "Nhóm 2"
    assert [stage["code"] for stage in rows["I36"]["stages"]] == ["PILE-REPAIR"]
    assert rows["I-40-42"]["record_origin"] == "MANUAL_ENTRY"
    assert "ADDITIONAL_SCOPE" in rows["I-40-42"]["scopes"]

    assert [row["canonical_code"] for row in client.get(
        "/api/v1/projects/p1/progress?q=I-36"
    ).json()] == ["I36"]
    assert [row["canonical_code"] for row in client.get(
        "/api/v1/projects/p1/progress?type=beam&scope=ADDITIONAL_SCOPE"
    ).json()] == ["I-40-42"]
    assert client.get(
        "/api/v1/projects/p1/progress?construction_status=COMPLETED"
    ).json() == []
    assert [row["canonical_code"] for row in client.get(
        "/api/v1/projects/p1/progress?acceptance_status=NOT_LINKED"
    ).json()] == ["I-40-42", "I36"]


def test_acceptance_status_uses_explicit_links_only(client, seeded):
    with seeded() as db:
        db.add(
            AcceptanceRequest(
                id="req-draft",
                project_id="p1",
                number="YC-002",
                status="draft",
            )
        )
        db.add(
            AcceptanceRequest(
                id="req-approved",
                project_id="p1",
                number="YC-001",
                status="confirmed",
            )
        )
        db.flush()
        db.add(
            AcceptanceRecord(
                id="rec-approved",
                project_id="p1",
                request_id="req-approved",
                number="BB-001",
                status="confirmed",
                result="approved",
                confirmed_at=datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.flush()
        db.add_all(
            [
                ComponentAcceptanceLink(
                    id="link-record",
                    project_id="p1",
                    component_id="c1",
                    record_id="rec-approved",
                    created_by="test-user",
                ),
                ComponentAcceptanceLink(
                    id="link-request",
                    project_id="p1",
                    component_id="c2",
                    request_id="req-draft",
                    created_by="test-user",
                ),
            ]
        )
        db.commit()

    rows = {
        row["canonical_code"]: row
        for row in client.get("/api/v1/projects/p1/progress").json()
    }
    assert rows["I36"]["acceptance_status"] == "APPROVED"
    assert rows["I36"]["acceptance_count"] == 1
    assert rows["I-40-42"]["acceptance_status"] == "PENDING"
    assert rows["I-40-42"]["acceptance_count"] == 0
    assert [row["canonical_code"] for row in client.get(
        "/api/v1/projects/p1/progress?acceptance_status=APPROVED"
    ).json()] == ["I36"]
    assert [row["canonical_code"] for row in client.get(
        "/api/v1/projects/p1/progress?acceptance_status=NOT_LINKED"
    ).json()] == []


def test_bulk_preview_is_exact_and_writes_nothing(client, seeded):
    response = client.post(
        "/api/v1/projects/p1/progress/bulk-preview",
        json=_bulk(component_ids=["c1", "c2", "c-other"]),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 2
    assert sorted(row["id"] for row in data["components"]) == ["c1", "c2"]
    assert data["missing_component_ids"] == ["c-other"]
    assert data["missing_stage_component_ids"] == ["c2"]
    assert data["can_commit"] is False
    assert data["warnings"]

    with seeded() as db:
        assert db.scalar(select(func.count(SiteProgressBulkBatch.id))) == 0
        assert db.scalar(select(func.count(ProgressEvent.id))) == 0

    conflict = client.post(
        "/api/v1/projects/p1/progress/bulk",
        json=_commit(component_ids=["c1", "c2", "c-other"]),
    )
    assert conflict.status_code == 409
    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 0


def test_bulk_commit_requires_review_and_is_idempotent_without_acceptance_side_effect(
    client, seeded
):
    assert client.post(
        "/api/v1/projects/p1/progress/bulk",
        json={**_commit(), "reviewed": False},
    ).status_code == 422

    first = client.post("/api/v1/projects/p1/progress/bulk", json=_commit())
    assert first.status_code == 201, first.text
    first_data = first.json()
    assert first_data["created"] == 1
    assert first_data["events"][0]["component_id"] == "c1"

    retry = client.post("/api/v1/projects/p1/progress/bulk", json=_commit())
    assert retry.status_code == 201, retry.text
    assert retry.json()["batch_id"] == first_data["batch_id"]
    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 1
        assert db.scalar(select(func.count(SiteProgressBulkBatch.id))) == 1
        assert db.scalar(select(func.count(AcceptanceRecord.id))) == 0

    changed = client.post(
        "/api/v1/projects/p1/progress/bulk",
        json=_commit(status="IN_PROGRESS"),
    )
    assert changed.status_code == 409

    second = client.post(
        "/api/v1/projects/p1/progress/bulk",
        json=_commit(
            idempotency_key="bulk-2",
            stage_definition_id="sd2",
            component_ids=["c2"],
            event_date="2026-11-19",
            status="IN_PROGRESS",
        ),
    )
    assert second.status_code == 201, second.text

    rows = {
        row["canonical_code"]: row
        for row in client.get("/api/v1/projects/p1/progress").json()
    }
    assert rows["I36"]["construction_status"] == "COMPLETED"
    assert rows["I-40-42"]["construction_status"] == "IN_PROGRESS"
    assert rows["I36"]["acceptance_status"] == "NOT_LINKED"
    assert rows["I-40-42"]["acceptance_count"] == 0
    assert [row["canonical_code"] for row in client.get(
        "/api/v1/projects/p1/progress?construction_status=COMPLETED"
    ).json()] == ["I36"]


def test_journal_preview_uses_actual_events_and_real_acceptance(client, seeded):
    report = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-18",
        json={
            "status": "reviewed",
            "notes": "Ghi chú",
            "site_notes": {"weather": "Nắng", "difficulties": "Thiếu nước"},
            "manpower": [{"group_name": "Công nhân", "count": 3}],
            "work_logs": [{"work_name": "Đục bê tông", "location": "Cọc I36"}],
            "next_day_plans": [],
        },
    )
    assert report.status_code == 200, report.text

    assert client.post(
        "/api/v1/projects/p1/progress/bulk", json=_commit()
    ).status_code == 201

    with seeded() as db:
        db.add(
            ProgressEvent(
                id="other-day",
                component_id="c2",
                component_stage_id="st2",
                event_date=date(2026, 11, 19),
                status="COMPLETED",
                evidence_refs="[]",
                created_by="test-user",
            )
        )
        db.add(
            AcceptanceRequest(
                id="req1",
                project_id="p1",
                number="YC-001",
                status="confirmed",
            )
        )
        db.flush()
        db.add(
            AcceptanceRecord(
                id="rec1",
                project_id="p1",
                request_id="req1",
                number="BB-001",
                status="confirmed",
                result="approved",
                confirmed_at=datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

    response = client.get("/api/v1/projects/p1/journals/2026-11-18/preview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["reviewed_only"] is True
    assert data["daily_report"]["status"] == "reviewed"
    assert [event["component_id"] for event in data["construction_events"]] == ["c1"]
    assert [event["number"] for event in data["acceptance_events"]] == ["BB-001"]
    assert data["journal"]["weather"] == "Nắng"
    assert data["journal"]["issues"] == "Thiếu nước"
    assert data["journal"]["manpower"][0]["count"] == 3
    assert any(item["source"] == "daily_report" for item in data["journal"]["work"])
    assert any(item["source"] == "progress_event" for item in data["journal"]["work"])
    assert "design_changes" in data["blank_sections"]
    assert "environment" in data["blank_sections"]
    assert data["journal"]["design_changes"] is None
    assert data["journal"]["environment"] is None


def test_journal_preview_does_not_fabricate_missing_sections(client):
    response = client.get("/api/v1/projects/p1/journals/2026-11-20/preview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["daily_report"] is None
    assert data["construction_events"] == []
    assert data["acceptance_events"] == []
    assert "acceptance" in data["blank_sections"]
    assert "manpower" in data["blank_sections"]
    assert data["journal"]["acceptance"] == []
    assert any("Chưa có báo cáo ngày" in warning for warning in data["warnings"])


def _add_repeated_scope_component(Session):
    with Session() as db:
        db.add(
            StructuralComponent(
                id="c3",
                project_id="p1",
                segment_id="s1",
                type="pile",
                raw_code="I37",
                canonical_code="I37",
                verification="VERIFIED",
                record_origin="SEED_IMPORT",
                created_by="test-user",
            )
        )
        db.add_all(
            [
                RepairScope(
                    id="sc3",
                    component_id="c3",
                    kind="DESIGN_SCOPE",
                    verification="VERIFIED",
                ),
                RepairScope(
                    id="sc4",
                    component_id="c3",
                    kind="ADDITIONAL_SCOPE",
                    verification="VERIFIED",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                ComponentStage(
                    id="st3",
                    component_id="c3",
                    stage_definition_id="sd1",
                    repair_scope_id="sc3",
                    created_by="test-user",
                ),
                ComponentStage(
                    id="st4",
                    component_id="c3",
                    stage_definition_id="sd1",
                    repair_scope_id="sc4",
                    created_by="test-user",
                ),
            ]
        )
        db.commit()


def test_bulk_requires_explicit_stage_when_definition_repeats_across_scopes(client, seeded):
    _add_repeated_scope_component(seeded)

    preview = client.post(
        "/api/v1/projects/p1/progress/bulk-preview",
        json=_bulk(component_ids=["c3"]),
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["can_commit"] is False
    assert data["ambiguous_stage_component_ids"] == ["c3"]
    row = data["components"][0]
    assert row["stage_ambiguous"] is True and row["stage_id"] is None
    assert {stage["id"] for stage in row["stage_options"]} == {"st3", "st4"}
    assert {stage["scope_kind"] for stage in row["stage_options"]} == {
        "DESIGN_SCOPE",
        "ADDITIONAL_SCOPE",
    }

    chosen = [{"component_id": "c3", "stage_id": "st4"}]
    selected = client.post(
        "/api/v1/projects/p1/progress/bulk-preview",
        json=_bulk(component_ids=["c3"], stage_selections=chosen),
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["can_commit"] is True
    assert selected.json()["ambiguous_stage_component_ids"] == []
    assert selected.json()["components"][0]["stage_id"] == "st4"

    invalid = client.post(
        "/api/v1/projects/p1/progress/bulk-preview",
        json=_bulk(
            component_ids=["c3"],
            stage_selections=[{"component_id": "c3", "stage_id": "st1"}],
        ),
    )
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["invalid_stage_component_ids"] == ["c3"]
    assert invalid.json()["can_commit"] is False

    assert client.post(
        "/api/v1/projects/p1/progress/bulk-preview",
        json=_bulk(
            component_ids=["c1"],
            stage_selections=[{"component_id": "c2", "stage_id": "st2"}],
        ),
    ).status_code == 422

    assert client.post(
        "/api/v1/projects/p1/progress/bulk",
        json=_commit(component_ids=["c3"], idempotency_key="amb-0"),
    ).status_code == 409
    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 0

    first = client.post(
        "/api/v1/projects/p1/progress/bulk",
        json=_commit(
            component_ids=["c3"], stage_selections=chosen, idempotency_key="amb-1"
        ),
    )
    assert first.status_code == 201, first.text
    assert first.json()["events"][0]["stage_id"] == "st4"
    retry = client.post(
        "/api/v1/projects/p1/progress/bulk",
        json=_commit(
            component_ids=["c3"], stage_selections=chosen, idempotency_key="amb-1"
        ),
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["batch_id"] == first.json()["batch_id"]
    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 1

    rows = {
        row["canonical_code"]: row
        for row in client.get("/api/v1/projects/p1/progress").json()
    }
    assert rows["I37"]["construction_event"]["stage_id"] == "st4"


def test_bulk_evidence_must_resolve_in_the_project(client, seeded):
    with seeded() as db:
        db.add_all(
            [
                SitePhoto(
                    id="ph1",
                    project_id="p1",
                    original_path="evidence.jpg",
                    sha256="a" * 64,
                    category="progress",
                ),
                SitePhoto(
                    id="ph2",
                    project_id="p1",
                    original_path="raw.jpg",
                    sha256="b" * 64,
                ),
                SitePhoto(
                    id="ph3",
                    project_id="other",
                    original_path="foreign.jpg",
                    sha256="c" * 64,
                    category="progress",
                ),
            ]
        )
        db.commit()

    url = "/api/v1/projects/p1/progress/bulk-preview"
    valid = _bulk(component_ids=["c1"], evidence_refs=["photo:ph1"])
    assert client.post(url, json=valid).status_code == 200
    assert client.post(
        url, json=_bulk(component_ids=["c1"], evidence_refs=["photo:ph3"])
    ).status_code == 404
    assert client.post(
        url, json=_bulk(component_ids=["c1"], evidence_refs=["photo:ph2"])
    ).status_code == 422
    assert client.post(
        url, json=_bulk(component_ids=["c1"], evidence_refs=["photo:missing"])
    ).status_code == 404
    assert client.post(
        url, json=_bulk(component_ids=["c1"], evidence_refs=["unknown:1"])
    ).status_code == 422

    commit_url = "/api/v1/projects/p1/progress/bulk"
    assert client.post(
        commit_url,
        json=_commit(component_ids=["c1"], evidence_refs=["photo:ph3"]),
    ).status_code == 404
    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 0
    first = client.post(commit_url, json=_commit(component_ids=["c1"], evidence_refs=["photo:ph1"]))
    assert first.status_code == 201, first.text
    assert first.json()["events"][0]["evidence_refs"] == ["photo:ph1"]


def test_daily_preview_is_read_only_and_project_scoped(client, seeded):
    response = client.post(
        "/api/v1/projects/p1/progress/daily-preview", json=_daily()
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["can_commit"] is True
    assert [line["line_index"] for line in data["lines"]] == [0, 1]
    assert data["lines"][0]["group_quantity"] == 12.5
    assert data["lines"][0]["group_unit"] == "m3"
    assert data["lines"][0]["components"][0]["id"] == "c1"
    assert data["lines"][1]["components"][0]["id"] == "c2"

    with seeded() as db:
        assert db.scalar(select(func.count(SiteProgressBulkBatch.id))) == 0
        assert db.scalar(select(func.count(ProgressEvent.id))) == 0

    scoped = client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json=_daily(
            lines=[
                *_daily()["lines"],
                _daily_line(stage_definition_id="sd1", component_ids=["c-other"]),
            ]
        ),
    )
    assert scoped.status_code == 200, scoped.text
    scoped_data = scoped.json()
    assert scoped_data["can_commit"] is False
    assert scoped_data["lines"][2]["missing_component_ids"] == ["c-other"]
    assert scoped_data["warnings"]
    assert client.post(
        "/api/v1/projects/p1/progress/daily",
        json=_daily_commit(
            idempotency_key="daily-scoped",
            lines=[_daily_line(component_ids=["c-other"])],
        ),
    ).status_code == 409

    foreign_stage = client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json=_daily(lines=[_daily_line(stage_definition_id="sd-other")]),
    )
    assert foreign_stage.status_code == 200, foreign_stage.text
    assert foreign_stage.json()["can_commit"] is False
    assert foreign_stage.json()["lines"][0]["missing_stage_component_ids"] == ["c1"]
    assert any(
        "không thuộc công trình" in warning
        for warning in foreign_stage.json()["warnings"]
    )


def test_daily_rejects_duplicate_resolved_stage_ids_across_lines(client, seeded):
    lines = [_daily_line(), _daily_line()]
    preview = client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json=_daily(lines=lines),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["can_commit"] is False
    assert any("trùng" in warning for warning in preview.json()["warnings"])

    conflict = client.post(
        "/api/v1/projects/p1/progress/daily",
        json=_daily_commit(lines=lines),
    )
    assert conflict.status_code == 409, conflict.text
    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 0
        assert db.scalar(select(func.count(SiteProgressBulkBatch.id))) == 0


def test_daily_commit_keeps_group_quantity_off_events_and_is_idempotent(
    client, seeded
):
    first = client.post("/api/v1/projects/p1/progress/daily", json=_daily_commit())
    assert first.status_code == 201, first.text
    first_data = first.json()
    assert first_data["created"] == 2
    assert [line["created"] for line in first_data["lines"]] == [1, 1]
    assert [line["group_quantity"] for line in first_data["lines"]] == [12.5, 0.0]
    assert all(
        event["quantity"] is None and event["unit"] is None
        for line in first_data["lines"]
        for event in line["events"]
    )

    retry = client.post("/api/v1/projects/p1/progress/daily", json=_daily_commit())
    assert retry.status_code == 201, retry.text
    assert retry.json() == first_data

    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 2
        assert all(
            event.quantity is None and event.unit is None
            for event in db.scalars(select(ProgressEvent))
        )
        batches = list(db.scalars(select(SiteProgressBulkBatch)))
        sentinel = next(
            batch for batch in batches if batch.idempotency_key == "daily-1"
        )
        stored = json.loads(sentinel.result_json)
        assert stored["created"] == 2
        assert stored["lines"][0]["group_quantity"] == 12.5
        assert stored["lines"][0]["group_unit"] == "m3"
        assert stored["lines"][1]["group_quantity"] == 0.0
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "component_progress_daily_recorded"
            )
        )
        detail = json.loads(audit.detail)
        assert detail["lines"][0]["group_quantity"] == 12.5
        assert detail["lines"][0]["group_unit"] == "m3"
        assert detail["lines"][1]["group_quantity"] == 0.0
        assert detail["lines"][0]["stage_ids"] == {"c1": "st1"}

    rows = {
        row["canonical_code"]: row
        for row in client.get("/api/v1/projects/p1/progress").json()
    }
    assert rows["I36"]["construction_status"] == "COMPLETED"
    assert rows["I-40-42"]["construction_status"] == "IN_PROGRESS"
    assert rows["I36"]["acceptance_status"] == "NOT_LINKED"

    changed = _daily_commit()
    changed["lines"] = [
        {**changed["lines"][0], "group_quantity": 99},
        changed["lines"][1],
    ]
    assert client.post(
        "/api/v1/projects/p1/progress/daily", json=changed
    ).status_code == 409
    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 2


def test_daily_commit_rolls_back_all_lines_when_a_later_line_fails(
    client, seeded, monkeypatch
):
    from app.site import progress as progress_module

    original = progress_module.commit_bulk
    calls = {"count": 0}

    def flaky_commit(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise progress_module.ProgressSelectionConflict("forced failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(progress_module, "commit_bulk", flaky_commit)
    response = client.post("/api/v1/projects/p1/progress/daily", json=_daily_commit())
    assert response.status_code == 409, response.text

    with seeded() as db:
        assert db.scalar(select(func.count(ProgressEvent.id))) == 0
        assert db.scalar(select(func.count(SiteProgressBulkBatch.id))) == 0
        assert db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "component_progress_daily_recorded"
            )
        ) == 0


def test_daily_commit_honours_explicit_stage_selection(client, seeded):
    _add_repeated_scope_component(seeded)
    line = _daily_line(
        stage_definition_id="sd1",
        component_ids=["c3"],
        stage_selections=[{"component_id": "c3", "stage_id": "st4"}],
    )
    preview = client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json=_daily(lines=[line]),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["can_commit"] is True
    assert preview.json()["lines"][0]["components"][0]["stage_id"] == "st4"

    saved = client.post(
        "/api/v1/projects/p1/progress/daily",
        json=_daily_commit(lines=[line], idempotency_key="daily-amb"),
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["lines"][0]["events"][0]["stage_id"] == "st4"


def test_daily_rejects_strict_date_and_workload_caps(client):
    tomorrow = (datetime.now(LOCAL_TZ).date() + timedelta(days=1)).isoformat()
    assert client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json={**_daily(), "event_date": tomorrow},
    ).status_code == 422
    assert client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json={**_daily(), "event_date": "18/11/2026"},
    ).status_code == 422

    too_many_lines = [_daily_line() for _ in range(51)]
    assert client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json=_daily(lines=too_many_lines),
    ).status_code == 422

    too_many_components = [
        _daily_line(component_ids=[f"x{i}" for i in range(251)]),
        _daily_line(component_ids=[f"y{i}" for i in range(251)]),
    ]
    assert client.post(
        "/api/v1/projects/p1/progress/daily-preview",
        json=_daily(lines=too_many_components),
    ).status_code == 422
