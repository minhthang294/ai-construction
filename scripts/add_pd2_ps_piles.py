"""Add the 19 PD2/Bunke additional-scope (phát sinh, PS) piles from the owner-approved
sketch "Mat_bang_PD2_va_bunke_phat_sinh_26-11" (dài×rộng in metres).

Each pile: Cầu chính segment 2 (same convention as the other Bunke-junction piles),
ADDITIONAL_SCOPE repair scope, stages = PS chipping + the main pile steps used by
PD2 (tẩy gỉ, vệ sinh, epoxy, rắc cát) copied from a reference PD2 pile, PS size
as design parameters, member of the "PD2 Cầu chính" batch. Idempotent, audited.
Preview by default; --commit writes.

Usage: python scripts/add_pd2_ps_piles.py --database URL --project NAME --actor USER_ID [--commit]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

PS = {  # code: [(dài, rộng), ...]
    "I54": [(0.5, 0.5)], "G53": [(0.75, 0.8)], "G56": [(0.7, 1.0)], "F51": [(0.4, 0.8)],
    "F58": [(0.5, 1.0)], "F63": [(0.3, 0.5)], "H86": [(0.9, 0.75)], "G74": [(0.9, 0.85)],
    "G77": [(0.5, 0.5)], "E157": [(0.3, 0.55)], "E158": [(1.1, 0.95)], "D154": [(1.3, 0.75)],
    "D155": [(1.1, 0.55)], "D158": [(0.5, 0.85)], "B157": [(0.7, 0.4)], "B158": [(1.2, 1.0)],
    "A156": [(0.9, 0.6)], "A157": [(0.9, 1.5), (0.9, 0.5)], "A158": [(1.2, 0.5)],
}
SOURCE = "Sơ đồ PD2 + Bunke phát sinh 26/11/2026"
REF_PILE = "I49"  # PD2 pile whose main-step definitions are reused
MAIN_STEPS = ("Tẩy gỉ cốt thép%", "Vệ sinh bề mặt%sau khi đục%", "Quét epoxy%", "Rắc cát tạo nhám%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--actor", required=True)
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()
    os.environ["DATABASE_URL"] = a.database
    from sqlalchemy import select, text
    from app.core.database import SessionLocal
    from app.core.models import AuditLog, now
    from app.core.component_models import (
        ComponentDesignParameter, ComponentStage, ConstructionBatch,
        ConstructionBatchComponent, RepairScope, StructuralComponent,
    )

    with SessionLocal() as db:
        pid = db.execute(text("select id from projects where name=:n"), {"n": a.project}).scalar_one()
        seg = db.execute(text("""select s.id from structure_segments s join structure_zones z on z.id=s.zone_id
            where z.project_id=:p and z.name='Cầu chính' and s.number=2"""), {"p": pid}).scalar_one()
        ps_def = db.execute(text("""select id from component_stage_definitions where project_id=:p
            and component_type='pile' and name like 'Đục bê tông om vỡ (phát sinh)%' order by position limit 1"""),
            {"p": pid}).scalar_one()
        ref = db.execute(text("select id from structural_components where project_id=:p and canonical_code=:c"),
                         {"p": pid, "c": REF_PILE}).scalar_one()
        step_defs = []
        for pat in MAIN_STEPS:
            ids = db.execute(text("""select st.stage_definition_id from component_stages st
                join component_stage_definitions d on d.id=st.stage_definition_id
                where st.component_id=:c and d.name like :pat"""), {"c": ref, "pat": pat}).scalars().all()
            assert len(ids) == 1, f"{REF_PILE}: expected one stage for {pat}, got {len(ids)}"
            step_defs.append(ids[0])
        batch = db.scalar(select(ConstructionBatch).where(
            ConstructionBatch.project_id == pid, ConstructionBatch.name == "PD2 Cầu chính"))
        assert batch, "batch 'PD2 Cầu chính' missing"

        existing = set(db.execute(text("select canonical_code from structural_components where project_id=:p"),
                                  {"p": pid}).scalars())
        todo = [c for c in PS if c not in existing]
        print(json.dumps({"to_create": todo, "already": sorted(set(PS) - set(todo))}, ensure_ascii=False))
        if not a.commit:
            return
        for code in todo:
            comp = StructuralComponent(project_id=pid, segment_id=seg, type="pile", raw_code=code,
                                       canonical_code=code, source_id=SOURCE, verification="VERIFIED",
                                       record_origin="MANUAL_ENTRY", created_by=a.actor)
            db.add(comp); db.flush()
            scope = RepairScope(component_id=comp.id, kind="ADDITIONAL_SCOPE", verification="VERIFIED",
                                approval_reference=SOURCE, reviewed_by=a.actor, reviewed_at=now())
            db.add(scope); db.flush()
            for did in (ps_def, *step_defs):
                db.add(ComponentStage(component_id=comp.id, stage_definition_id=did,
                                      repair_scope_id=scope.id, created_by=a.actor))
            for i, (dai, rong) in enumerate(PS[code], 1):
                sfx = "" if i == 1 else str(i)
                for name, value in ((f"ps_dai{sfx}_m", dai), (f"ps_rong{sfx}_m", rong)):
                    db.add(ComponentDesignParameter(project_id=pid, component_id=comp.id, name=name, value=value,
                                                    unit="m", source_drawing=SOURCE, created_by=a.actor))
            db.add(ConstructionBatchComponent(batch_id=batch.id, component_id=comp.id, added_by=a.actor,
                                              reason="Cọc phát sinh PD2/Bunke theo sơ đồ 26/11"))
        db.add(AuditLog(project_id=pid, actor_id=a.actor, action="pd2_ps_piles_added",
                        entity="StructuralComponent", entity_id=batch.id,
                        detail=json.dumps({"codes": todo, "source": SOURCE}, ensure_ascii=False)))
        db.commit()
        print("COMMITTED", len(todo))


if __name__ == "__main__":
    main()
