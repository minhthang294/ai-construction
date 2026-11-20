"""N-N component/stage/scope links to PYC and BBNT.

These tests use the shared component inventory and stage contract plus the
acceptance-owned ``ComponentAcceptanceLink`` table.  Design:
``docs/agent-reports/acceptance-component-links-design.md``.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select

from app.core.component_models import (
    ComponentStage,
    ComponentWorkLink,
    RepairScope,
    Segment,
    StageDefinition,
    StructuralComponent,
    StructureZone,
)
from app.core.models import User
from app.acceptance.models import ComponentAcceptanceLink
from conftest import create_record, create_request, seed_work_item


def _seed_user(client, project_id):
    with client.SessionLocal() as db:
        username = f"links-{project_id}-{uuid.uuid4().hex[:8]}"
        user = User(username=username, password_hash="test-only", role="engineer")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def _seed_component(client, project_id="p1", code="P-01", scope_kind="DESIGN_SCOPE"):
    """Create one verified component with one scope and one stage."""

    user_id = _seed_user(client, project_id)
    with client.SessionLocal() as db:
        zone = db.scalar(
            select(StructureZone).where(
                StructureZone.project_id == project_id,
                StructureZone.name_key == "khu a",
            )
        )
        if zone is None:
            zone = StructureZone(project_id=project_id, name="Khu A", name_key="khu a")
            db.add(zone)
            db.flush()
        segment = db.scalar(
            select(Segment).where(Segment.zone_id == zone.id, Segment.number == 1)
        )
        if segment is None:
            segment = Segment(zone_id=zone.id, number=1, source_code="PD1")
            db.add(segment)
            db.flush()
        definition = db.scalar(
            select(StageDefinition).where(
                StageDefinition.project_id == project_id,
                StageDefinition.component_type == "pile",
                StageDefinition.code == "PREP",
            )
        )
        if definition is None:
            definition = StageDefinition(
                project_id=project_id,
                component_type="pile",
                code="PREP",
                name="Chuẩn bị",
                position=1,
            )
            db.add(definition)
            db.flush()
        component = StructuralComponent(
            project_id=project_id,
            segment_id=segment.id,
            type="pile",
            raw_code=code,
            canonical_code=code,
            verification="VERIFIED",
            record_origin="MANUAL_ENTRY",
            created_by=user_id,
        )
        db.add(component)
        db.flush()
        scope = RepairScope(
            component_id=component.id,
            kind=scope_kind,
            verification="VERIFIED",
            revision=1,
        )
        db.add(scope)
        db.flush()
        stage = ComponentStage(
            component_id=component.id,
            stage_definition_id=definition.id,
            repair_scope_id=scope.id,
            created_by=user_id,
        )
        db.add(stage)
        db.commit()
        return component.id, stage.id, scope.id


def _seed_second_scope_and_stage(client, component_id):
    user_id = _seed_user(client, "p1")
    with client.SessionLocal() as db:
        definition = StageDefinition(
            project_id="p1",
            component_type="pile",
            code="FINISH",
            name="Hoàn thiện",
            position=2,
        )
        db.add(definition)
        db.flush()
        scope = RepairScope(
            component_id=component_id,
            kind="ADDITIONAL_SCOPE",
            verification="VERIFIED",
            revision=1,
        )
        db.add(scope)
        db.flush()
        stage = ComponentStage(
            component_id=component_id,
            stage_definition_id=definition.id,
            repair_scope_id=scope.id,
            created_by=user_id,
        )
        db.add(stage)
        db.commit()
        return stage.id, scope.id


def _seed_dm_link(client, component_id):
    with client.SessionLocal() as db:
        db.add(
            ComponentWorkLink(
                component_id=component_id,
                source_hash="a" * 64,
                dm_row=7,
                seed_row=7,
                work="Thí nghiệm liên kết tạm",
                raw_location="P-01",
            )
        )
        db.commit()


def _record_links(client, record_id):
    response = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record_id}/component-links"
    )
    assert response.status_code == 200, response.text
    return response.json()


def _request_links(client, request_id):
    response = client.get(
        f"/api/v1/projects/p1/acceptance-requests/{request_id}/component-links"
    )
    assert response.status_code == 200, response.text
    return response.json()


def _replace_record_links(client, record_id, links, reviewed=True):
    return client.put(
        f"/api/v1/projects/p1/acceptance-records/{record_id}/component-links",
        json={"reviewed": reviewed, "links": links},
    )


def _replace_request_links(client, request_id, links, reviewed=True):
    return client.put(
        f"/api/v1/projects/p1/acceptance-requests/{request_id}/component-links",
        json={"reviewed": reviewed, "links": links},
    )


def _payload(component_id, stage_id=None, scope_id=None):
    item = {"component_id": component_id}
    if stage_id is not None:
        item["stage_id"] = stage_id
    if scope_id is not None:
        item["scope_id"] = scope_id
    return item


def test_links_require_review_and_never_confirm_acceptance(client):
    request = create_request(client)
    record = create_record(client, request["id"], checklist=[])
    component_id, stage_id, scope_id = _seed_component(client)

    preview_before = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/preview"
    )
    assert preview_before.status_code == 200, preview_before.text

    rejected = _replace_record_links(
        client,
        record["id"],
        [_payload(component_id, stage_id, scope_id)],
        reviewed=False,
    )
    assert rejected.status_code == 422
    assert _record_links(client, record["id"]) == []

    accepted = _replace_record_links(
        client, record["id"], [_payload(component_id, stage_id, scope_id)]
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()[0]["stage_id"] == stage_id
    assert accepted.json()[0]["scope_id"] == scope_id

    fetched = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}"
    ).json()
    assert fetched["status"] == "draft"
    assert fetched["result"] is None
    assert {item["state"] for item in fetched["checklist"]} == {"unconfirmed"}

    preview_after = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/preview"
    )
    assert preview_after.status_code == 200, preview_after.text
    assert preview_after.json()["cells"] == preview_before.json()["cells"]


def test_links_are_deterministic_and_repeatable(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    second_id, second_stage, second_scope = _seed_component(client, code="P-02")
    first_id, first_stage, first_scope = _seed_component(client, code="P-01")
    payload = [
        _payload(second_id, second_stage, second_scope),
        _payload(first_id, first_stage, first_scope),
    ]

    first = _replace_record_links(client, record["id"], payload)
    assert first.status_code == 200, first.text
    assert [item["component_id"] for item in first.json()] == [first_id, second_id]

    repeated = _replace_record_links(client, record["id"], payload)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == first.json()
    assert _record_links(client, record["id"]) == first.json()

    deduplicated = _replace_record_links(
        client, record["id"], [payload[0], payload[0]]
    )
    assert deduplicated.status_code == 200, deduplicated.text
    assert [item["component_id"] for item in deduplicated.json()] == [second_id]


def test_one_record_links_many_components_and_one_component_links_many_records(client):
    request_one = create_request(client, number="101")
    request_two = create_request(client, number="102")
    record_one = create_record(client, request_one["id"])
    record_two = create_record(client, request_two["id"])
    first_id, first_stage, first_scope = _seed_component(client, code="P-01")
    second_id, second_stage, second_scope = _seed_component(client, code="P-02")

    assert _replace_record_links(
        client,
        record_one["id"],
        [
            _payload(first_id, first_stage, first_scope),
            _payload(second_id, second_stage, second_scope),
        ],
    ).status_code == 200
    assert _replace_record_links(
        client, record_two["id"], [_payload(first_id, first_stage, first_scope)]
    ).status_code == 200

    assert [item["component_id"] for item in _record_links(client, record_one["id"])] == [
        first_id,
        second_id,
    ]
    assert [item["component_id"] for item in _record_links(client, record_two["id"])] == [
        first_id
    ]


def test_request_and_record_links_are_independent(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    first_id, first_stage, first_scope = _seed_component(client, code="P-01")
    second_id, second_stage, second_scope = _seed_component(client, code="P-02")

    assert _replace_request_links(
        client, request["id"], [_payload(first_id, first_stage, first_scope)]
    ).status_code == 200
    assert _record_links(client, record["id"]) == []

    assert _replace_record_links(
        client, record["id"], [_payload(second_id, second_stage, second_scope)]
    ).status_code == 200
    assert [item["component_id"] for item in _request_links(client, request["id"])] == [
        first_id
    ]
    assert [item["component_id"] for item in _record_links(client, record["id"])] == [
        second_id
    ]


def test_links_reject_cross_project_and_mismatched_links_atomically(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    local_id, local_stage, local_scope = _seed_component(
        client, project_id="p1", code="P-01"
    )
    foreign_id, foreign_stage, foreign_scope = _seed_component(
        client, project_id="p2", code="P-01"
    )

    cross_project = _replace_record_links(
        client,
        record["id"],
        [
            _payload(local_id, local_stage, local_scope),
            _payload(foreign_id, foreign_stage, foreign_scope),
        ],
    )
    assert cross_project.status_code in (404, 409)
    assert _record_links(client, record["id"]) == []

    mismatched_scope = _replace_record_links(
        client, record["id"], [_payload(local_id, local_stage, foreign_scope)]
    )
    assert mismatched_scope.status_code == 409
    assert _record_links(client, record["id"]) == []

    mismatched_stage = _replace_record_links(
        client, record["id"], [_payload(local_id, foreign_stage, local_scope)]
    )
    assert mismatched_stage.status_code == 409
    assert _record_links(client, record["id"]) == []

    unknown_stage = _replace_record_links(
        client,
        record["id"],
        [_payload(local_id, "missing-stage", local_scope)],
    )
    assert unknown_stage.status_code in (404, 409)
    assert _record_links(client, record["id"]) == []


def test_stage_must_match_the_selected_scope(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    component_id, stage_id, _scope_id = _seed_component(client)
    _other_stage, other_scope = _seed_second_scope_and_stage(client, component_id)

    mismatched = _replace_record_links(
        client, record["id"], [_payload(component_id, stage_id, other_scope)]
    )
    assert mismatched.status_code == 409
    assert _record_links(client, record["id"]) == []


def test_confirmed_record_rejects_link_changes(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    component_id, stage_id, scope_id = _seed_component(client)
    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text

    rejected = _replace_record_links(
        client, record["id"], [_payload(component_id, stage_id, scope_id)]
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "record_confirmed"
    assert _record_links(client, record["id"]) == []


def test_revision_does_not_inherit_links_without_explicit_review(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    component_id, stage_id, scope_id = _seed_component(client)
    assert _replace_record_links(
        client, record["id"], [_payload(component_id, stage_id, scope_id)]
    ).status_code == 200

    revision = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/revisions"
    )
    assert revision.status_code == 201, revision.text
    revision_id = revision.json()["id"]

    assert _record_links(client, revision_id) == []
    assert [item["component_id"] for item in _record_links(client, record["id"])] == [
        component_id
    ]

    copied = _replace_record_links(
        client, revision_id, [_payload(component_id, stage_id, scope_id)]
    )
    assert copied.status_code == 200, copied.text
    assert [item["component_id"] for item in copied.json()] == [component_id]


def test_work_item_and_dm_links_do_not_auto_create_component_links(client):
    work_item_id = seed_work_item(client, "p1", code="W-LINK", name="Hạng mục liên kết")
    component_id, _stage_id, _scope_id = _seed_component(client)
    _seed_dm_link(client, component_id)
    request = create_request(client, work_item_id=work_item_id)
    record = create_record(client, request["id"], checklist=[])

    assert _request_links(client, request["id"]) == []
    assert _record_links(client, record["id"]) == []


def test_link_payload_keeps_only_reviewed_links(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    first_id, first_stage, first_scope = _seed_component(client, code="P-01")
    second_id, second_stage, second_scope = _seed_component(client, code="P-02")

    assert _replace_record_links(
        client,
        record["id"],
        [
            _payload(first_id, first_stage, first_scope),
            _payload(second_id, second_stage, second_scope),
        ],
    ).status_code == 200
    replaced = _replace_record_links(
        client, record["id"], [_payload(second_id, second_stage, second_scope)]
    )
    assert replaced.status_code == 200, replaced.text
    assert [item["component_id"] for item in replaced.json()] == [second_id]
    assert [item["component_id"] for item in _record_links(client, record["id"])] == [
        second_id
    ]


def test_link_payload_uses_the_same_missing_record_error_as_other_routes(client):
    component_id, stage_id, scope_id = _seed_component(client)
    missing = _replace_record_links(
        client, "missing-record", [_payload(component_id, stage_id, scope_id)]
    )
    assert missing.status_code == 404


def test_force_deleting_pyc_removes_request_and_record_links(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    component_id, stage_id, scope_id = _seed_component(client)
    payload = [_payload(component_id, stage_id, scope_id)]
    assert _replace_request_links(client, request["id"], payload).status_code == 200
    assert _replace_record_links(client, record["id"], payload).status_code == 200

    deleted = client.delete(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}",
        params={"force": True},
    )
    assert deleted.status_code == 204, deleted.text

    with client.SessionLocal() as db:
        remaining = db.scalar(
            select(ComponentAcceptanceLink).where(
                ComponentAcceptanceLink.project_id == "p1"
            )
        )
        assert remaining is None


def test_component_links_each_repair_scope_independently(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    component_id, stage_id, scope_id = _seed_component(client)
    other_stage_id, other_scope_id = _seed_second_scope_and_stage(client, component_id)

    response = _replace_record_links(
        client,
        record["id"],
        [
            _payload(component_id, stage_id, scope_id),
            _payload(component_id, other_stage_id, other_scope_id),
        ],
    )
    assert response.status_code == 200, response.text
    assert [item["scope_id"] for item in response.json()] == [scope_id, other_scope_id]
    assert [item["scope_kind"] for item in response.json()] == [
        "DESIGN_SCOPE",
        "ADDITIONAL_SCOPE",
    ]
    assert [item["stage_id"] for item in response.json()] == [stage_id, other_stage_id]
    assert response.json() == _record_links(client, record["id"])


def test_links_survive_pyc_submit_and_bbnt_confirm_then_record_is_frozen(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    component_id, stage_id, scope_id = _seed_component(client)
    payload = [_payload(component_id, stage_id, scope_id)]
    assert _replace_request_links(client, request["id"], payload).status_code == 200
    assert _replace_record_links(client, record["id"], payload).status_code == 200

    submitted = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}",
        json={"status": "submitted"},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert [item["component_id"] for item in _request_links(client, request["id"])] == [
        component_id
    ]

    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["result"] == "approved"
    assert [item["component_id"] for item in _record_links(client, record["id"])] == [
        component_id
    ]

    frozen = _replace_record_links(client, record["id"], [])
    assert frozen.status_code == 409
    assert frozen.json()["code"] == "record_confirmed"
    assert _record_links(client, record["id"])[0]["component_id"] == component_id


def test_linking_does_not_change_the_template_or_block_export(client, template_path):
    before = hashlib.sha256(template_path.read_bytes()).hexdigest()
    request = create_request(client)
    record = create_record(client, request["id"])
    component_id, stage_id, scope_id = _seed_component(client)
    assert _replace_record_links(
        client, record["id"], [_payload(component_id, stage_id, scope_id)]
    ).status_code == 200

    assert hashlib.sha256(template_path.read_bytes()).hexdigest() == before

    preview = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/preview"
    )
    assert preview.status_code == 200, preview.text

    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text

    exported = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports",
        json={"kind": "bbnt", "format": "xlsx"},
    )
    assert exported.status_code == 201, exported.text
    assert exported.json()["template_sha256"] == before
    assert hashlib.sha256(template_path.read_bytes()).hexdigest() == before
