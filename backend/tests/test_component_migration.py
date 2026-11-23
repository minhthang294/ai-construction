import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_component_migration_round_trip_preserves_existing_project(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}

    def migrate(*args):
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend, env=env,
                       check=True, capture_output=True, text=True)

    migrate("upgrade", "a7c3e9f2b641")
    with sqlite3.connect(db_path) as db:
        db.execute("insert into projects (id, name, status, created_at) values ('p', 'kept', 'active', '2026-01-01')")
    migrate("upgrade", "head")
    migrate("downgrade", "a7c3e9f2b641")
    migrate("upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute("select name from projects where id='p'").fetchone() == ("kept",)
        assert db.execute("select name from sqlite_master where type='table' and name='structural_components'").fetchone()


def test_design_parameters_migration_round_trip_preserves_component(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "design-parameters-migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}

    def migrate(*args):
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend, env=env,
                       check=True, capture_output=True, text=True)

    migrate("upgrade", "a1b2c3d4e5f6")
    with sqlite3.connect(db_path) as db:
        db.execute("insert into users (id, username, password_hash, role) values ('u', 'u', 'x', 'admin')")
        db.execute("insert into projects (id, name, status, created_at) values ('p', 'kept', 'active', '2026-01-01')")
        db.execute("insert into structure_zones (id, project_id, name, name_key) values ('z', 'p', 'Zone', 'zone')")
        db.execute("insert into structure_segments (id, zone_id, number, source_code) values ('s', 'z', 1, 'S1')")
        db.execute("insert into structural_components (id, project_id, segment_id, type, raw_code, canonical_code,"
                   " verification, record_origin, created_by, created_at)"
                   " values ('c', 'p', 's', 'pile', 'P1', 'P1', 'VERIFIED', 'SEED_IMPORT', 'u', '2026-01-01')")
        db.commit()

    migrate("upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute("select name from sqlite_master where type='table' and name='component_design_parameters'").fetchone()
        db.execute("insert into component_design_parameters (id, project_id, component_id, name, value, unit,"
                   " created_by, created_at) values ('dp', 'p', 'c', 't_cm', 3, 'cm', 'u', '2026-01-02')")
        db.commit()

    migrate("downgrade", "a1b2c3d4e5f6")
    with sqlite3.connect(db_path) as db:
        assert db.execute("select name from sqlite_master where type='table' and name='component_design_parameters'").fetchone() is None
        assert db.execute("select canonical_code from structural_components where id='c'").fetchone() == ("P1",)

    migrate("upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute("select name from sqlite_master where type='table' and name='component_design_parameters'").fetchone()


def test_photo_component_links_migration_moves_and_restores_encoded_values(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "photo-components-migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}

    def migrate(*args):
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend, env=env,
                       check=True, capture_output=True, text=True)

    migrate("upgrade", "b7c8d9e0f1a2")
    encoded = '@components:{"ids":["c1","c2"],"label":"P1, P2"}'
    with sqlite3.connect(db_path) as db:
        db.execute("insert into users (id, username, password_hash, role) values ('u', 'u', 'x', 'admin')")
        db.execute("insert into projects (id, name, status, created_at) values ('p', 'kept', 'active', '2026-01-01')")
        db.execute("insert into structure_zones (id, project_id, name, name_key) values ('z', 'p', 'Zone', 'zone')")
        db.execute("insert into structure_segments (id, zone_id, number, source_code) values ('s', 'z', 1, 'S1')")
        for component_id, code in (("c1", "P1"), ("c2", "P2")):
            db.execute(
                "insert into structural_components (id, project_id, segment_id, type, raw_code, canonical_code,"
                " verification, record_origin, created_by, created_at)"
                " values (?, 'p', 's', 'pile', ?, ?, 'VERIFIED', 'SEED_IMPORT', 'u', '2026-01-01')",
                (component_id, code, code),
            )
        db.execute(
            "insert into site_photos (id, project_id, original_path, sha256, upload_time, component,"
            " created_at, updated_at) values ('ph', 'p', '/tmp/ph.jpg', 'sha', '2026-01-02', ?,"
            " '2026-01-02', '2026-01-02')",
            (encoded,),
        )
        db.commit()

    migrate("upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "select name from sqlite_master where type='table' and name='site_photo_components'"
        ).fetchone()
        assert db.execute(
            "select component_id from site_photo_components where photo_id='ph' order by component_id"
        ).fetchall() == [("c1",), ("c2",)]
        assert db.execute("select component from site_photos where id='ph'").fetchone() == (None,)

    migrate("downgrade", "b7c8d9e0f1a2")
    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "select name from sqlite_master where type='table' and name='site_photo_components'"
        ).fetchone() is None
        restored = db.execute("select component from site_photos where id='ph'").fetchone()[0]
        assert restored.startswith("@components:")
        assert '"c1"' in restored and '"c2"' in restored

    migrate("upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "select component_id from site_photo_components where photo_id='ph' order by component_id"
        ).fetchall() == [("c1",), ("c2",)]
        assert db.execute("select component from site_photos where id='ph'").fetchone() == (None,)


def test_progress_migration_is_additive_and_preserves_component_data(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "progress-migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}

    def migrate(*args):
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend, env=env,
                       check=True, capture_output=True, text=True)

    migrate("upgrade", "170f7a3596cf")
    with sqlite3.connect(db_path) as db:
        db.execute("insert into users (id, username, password_hash, role) values ('u', 'u', 'x', 'admin')")
        db.execute("insert into projects (id, name, status, created_at) values ('p', 'kept', 'active', '2026-01-01')")
        db.execute("insert into structure_zones (id, project_id, name, name_key) values ('z', 'p', 'Zone', 'zone')")
        db.execute("insert into structure_segments (id, zone_id, number, source_code) values ('s', 'z', 1, 'S1')")
        db.execute("insert into structural_components (id, project_id, segment_id, type, raw_code, canonical_code,"
                   " verification, record_origin, created_by, created_at)"
                   " values ('c', 'p', 's', 'pile', 'P1', 'P1', 'VERIFIED', 'SEED_IMPORT', 'u', '2026-01-01')")
        db.execute("insert into component_repair_scopes (id, component_id, kind, verification, revision)"
                   " values ('r', 'c', 'DESIGN_SCOPE', 'VERIFIED', 1)")
        db.commit()

    migrate("upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute("select canonical_code from structural_components where id='c'").fetchone() == ("P1",)
        assert db.execute("select revision from component_repair_scopes where id='r'").fetchone() == (1,)
        for table in ("component_stage_definitions", "component_stages", "component_progress_events",
                      "component_progress_batches", "component_acceptance_links"):
            assert db.execute("select name from sqlite_master where type='table' and name=?", (table,)).fetchone()
        db.execute("insert into component_stage_definitions (id, project_id, component_type, code, name, position)"
                   " values ('d', 'p', 'pile', 'SP', 'Surface prep', 1)")
        db.execute("insert into component_repair_scopes (id, component_id, kind, verification, revision)"
                   " values ('r2', 'c', 'ADDITIONAL_SCOPE', 'NEEDS_REVIEW', 1)")
        db.execute("insert into component_stages (id, component_id, stage_definition_id, repair_scope_id,"
                   " created_by, created_at) values ('st', 'c', 'd', 'r', 'u', '2026-01-02')")
        db.execute("insert into component_stages (id, component_id, stage_definition_id, repair_scope_id,"
                   " created_by, created_at) values ('st2', 'c', 'd', 'r2', 'u', '2026-01-02')")
        db.commit()
        try:
            db.execute("insert into component_stages (id, component_id, stage_definition_id, repair_scope_id,"
                       " created_by, created_at) values ('st3', 'c', 'd', 'r', 'u', '2026-01-02')")
            db.commit()
            raise AssertionError("duplicate stage in the same scope must be rejected")
        except sqlite3.IntegrityError:
            db.rollback()
        db.execute("insert into component_progress_events (id, component_id, component_stage_id, event_date,"
                   " status, quantity, unit, note, evidence_refs, created_by, created_at)"
                   " values ('e', 'c', 'st', '2026-01-02', 'IN_PROGRESS', 1.5, 'm3', null, '[]', 'u', '2026-01-02')")
        db.execute("insert into component_progress_batches (id, project_id, idempotency_key, payload_hash,"
                   " created_at) values ('b', 'p', 'k', 'h', '2026-01-02')")
        db.commit()

    migrate("downgrade", "170f7a3596cf")
    with sqlite3.connect(db_path) as db:
        assert db.execute("select canonical_code from structural_components where id='c'").fetchone() == ("P1",)
        assert db.execute("select revision from component_repair_scopes where id='r'").fetchone() == (1,)
        for table in ("component_stage_definitions", "component_stages", "component_progress_events",
                      "component_progress_batches", "component_acceptance_links"):
            assert db.execute("select name from sqlite_master where type='table' and name=?", (table,)).fetchone() is None

    migrate("upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute("select canonical_code from structural_components where id='c'").fetchone() == ("P1",)
