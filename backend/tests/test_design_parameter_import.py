"""Preview/commit tests for reviewed design-parameter CSV import."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core import database
from app.core.component_models import (
    ComponentAlias,
    ComponentDesignParameter,
    Segment,
    StructuralComponent,
    StructureZone,
)
from app.core.design_parameter_import import commit_import, prepare_import
from app.core.models import AuditLog, Project, User

HEADER = (
    "page;drawing;subgroup;source_data_row;zone_printed;code_printed;"
    "L1_m;L2_m;L3_m;L4_m;t_cm;n;a_mm;b_m;review_status"
)


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'params.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    database.Base.metadata.create_all(engine)
    with factory() as db:
        user = User(username="param-admin", password_hash="x", role="admin")
        project = Project(name="Param project", status="active")
        db.add_all([user, project])
        db.flush()
        zone = StructureZone(project_id=project.id, name="Cầu chính", name_key="cầu chính")
        db.add(zone)
        db.flush()
        segments = {}
        for number in (1, 2):
            segment = Segment(zone_id=zone.id, number=number, source_code=f"S{number}")
            db.add(segment)
            segments[number] = segment
        db.flush()
        db.commit()
        yield factory, project.id, user.id, segments


def _component(db, project_id, user_id, segment, code, aliases=()):
    component = StructuralComponent(
        project_id=project_id, segment_id=segment.id, type="pile", raw_code=code,
        canonical_code=code, verification="VERIFIED", record_origin="MANUAL_ENTRY",
        created_by=user_id)
    db.add(component)
    db.flush()
    for alias in (code, *aliases):
        db.add(ComponentAlias(component_id=component.id, project_id=project_id,
                              segment_id=segment.id, type="pile", alias=alias))
    db.flush()
    return component


def _csv(tmp_path, rows):
    path = tmp_path / "params.csv"
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return str(path)


def test_preview_commit_and_idempotency(env, tmp_path):
    factory, project_id, user_id, segments = env
    with factory() as db:
        component = _component(db, project_id, user_id, segments[1], "P1", ("AL1",))
        db.commit()
    path = _csv(tmp_path, [
        "25;TK-19;II.1;1;Cầu chính;AL1;0,5;0,1;0,6;0,55;3;;;;"
    ])
    with factory() as db:
        preview = prepare_import(db, project_id, path)
        assert preview["csv_rows"] == 1
        assert preview["matched_components"] == 1
        assert preview["unmatched"] == []
        assert {item["name"] for item in preview["parameters"]} == {
            "L1_m", "L2_m", "L3_m", "L4_m", "t_cm"
        }
        summary = commit_import(db, preview, user_id)
        assert summary["inserted"] == 5
        assert db.scalar(select(AuditLog).where(
            AuditLog.action == "component_design_parameters_imported")) is not None
        stored = db.scalars(select(ComponentDesignParameter).where(
            ComponentDesignParameter.component_id == component.id))
        assert {item.name: item.value for item in stored}["t_cm"] == 3

        again = prepare_import(db, project_id, path)
        assert again["parameters"] == []
        assert again["unchanged"] == 5
        assert commit_import(db, again, user_id)["inserted"] == 0


def test_unmatched_ambiguous_and_conflicting_rows_are_not_imported(env, tmp_path):
    factory, project_id, user_id, segments = env
    with factory() as db:
        ok = _component(db, project_id, user_id, segments[1], "P2")
        _component(db, project_id, user_id, segments[1], "DUP")
        _component(db, project_id, user_id, segments[2], "DUP")
        bad = _component(db, project_id, user_id, segments[1], "X1")
        db.commit()
    path = _csv(tmp_path, [
        "25;TK-19;II.1;1;Cầu chính;P2;0,5;;;;2;;;;",
        "25;TK-19;II.1;2;Cầu chính;DUP;0,5;;;;3;;;;",
        "25;TK-19;II.1;3;Cầu chính;X1;0,5;;;;3;;;;",
        "25;TK-19;II.1;4;Cầu chính;X1;0,5;;;;5;;;;",
        "25;TK-19;II.1;5;Cầu chính;Z9;0,5;;;;3;;;;",
    ])
    with factory() as db:
        preview = prepare_import(db, project_id, path)
        assert preview["matched_components"] == 2  # P2 + X1 conflict is removed from planned
        assert len(preview["ambiguous"]) == 1
        assert len(preview["conflicts"]) == 1
        assert preview["conflicts"][0]["code"] == "X1"
        assert preview["unmatched"][0]["code"] == "Z9"
        assert {item["component_id"] for item in preview["parameters"]} == {ok.id}
        commit_import(db, preview, user_id)
        assert db.scalar(select(ComponentDesignParameter).where(
            ComponentDesignParameter.component_id == bad.id)) is None


def test_existing_different_value_is_conflict_not_overwrite(env, tmp_path):
    factory, project_id, user_id, segments = env
    with factory() as db:
        component = _component(db, project_id, user_id, segments[1], "P3")
        db.add(ComponentDesignParameter(
            project_id=project_id, component_id=component.id, name="t_cm",
            value=3, unit="cm", created_by=user_id,
            created_at=datetime.now(timezone.utc)))
        db.commit()
    path = _csv(tmp_path, [
        "25;TK-19;II.1;1;Cầu chính;P3;;;;;4;;;;"
    ])
    with factory() as db:
        preview = prepare_import(db, project_id, path)
        assert preview["parameters"] == []
        assert len(preview["conflicts"]) == 1
        assert preview["conflicts"][0]["values"]["t_cm"] == [3, 4]
        commit_import(db, preview, user_id)
        stored = db.scalar(select(ComponentDesignParameter).where(
            ComponentDesignParameter.component_id == component.id,
            ComponentDesignParameter.name == "t_cm"))
        assert stored.value == 3
