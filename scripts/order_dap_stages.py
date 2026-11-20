"""Preview or apply the reviewed DAP display sequence to one SQLite database."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


JACKET_LABEL = "Lắp tấm vỏ composite tiền chế"
JACKET_SOURCE = "tấm vỏ composite tiền chế sợi carbon"

PILE_PHASES = (
    ("đục hà bám", "thợ lặn phục vụ"),
    ("đục bê tông",),
    ("tẩy gỉ", "vệ sinh bề mặt cọc sau khi đục", "vệ sinh bề mặt sau khi đục"),
    ("khoan lỗ d30", "keo gắn cấy thép", "cốt thép bổ sung", "đường hàn"),
    ("mài tạo phẳng và vệ sinh bề mặt cọc", "quét epoxy hm-180", "rắc cát"),
    ("vệ sinh bằng nước sạch", "vệ sinh bề mặt cọc trong phạm vi 50"),
    (JACKET_LABEL.casefold(),),
    ("lỗ khoan 3,5", "quét keo hm-500", "đinh rút"),
    ("hút nước khỏi vỏ",),
    ("vữa không co ngót",),
    ("trám vá đầu cọc",),
    ("mài tạo phẳng và vệ sinh trong phạm vi dán sợi", "mài phẳng và vệ sinh vùng dán sợi", "trám vá trong phạm vi dán sợi", "trám vá vùng dán sợi"),
    ("dán ướt sợi carbon dày 1 mm tấm t1", "dán ướt sợi carbon dày 1 mm tấm t2", "dán ướt sợi carbon dày 1 mm tấm t3"),
    ("hệ sơn bảo vệ", "sơn bảo vệ"),
    ("vận chuyển đổ thải",),
)

BEAM_PHASES = (
    ("đục bê tông",),
    ("vệ sinh bề mặt", "tẩy gỉ"),
    ("khoan lỗ gắn thép", "keo gắn cấy cốt thép", "cốt thép bổ sung", "thay thế, bổ sung cốt thép", "đường hàn"),
    ("quét epoxy bám dính", "quét epoxy hm-180c3p hoặc tương đương, 0,8", "quét dính bám sumen latex"),
    ("rắc cát", "phủ cát", "trám sumen mortar"),
    ("ván khuôn", "đục lỗ 100", "quét chất dính bám bê tông cũ và mới trong lỗ"),
    ("vữa không co ngót",),
    ("trám lỗ", "trám phẳng đáy dầm"),
    ("mài vệ sinh bê tông trong", "trám phẳng bằng sumendur80", "trám phẳng sumendur80 trong vùng dán sợi"),
    ("dán tấm sợi thủy tinh 0,635 mm lớp 1", "tấm sợi thủy tinh dày 0,635 mm lớp 1", "dán tấm sợi thủy tinh 0,635 mm lớp 2", "tấm sợi thủy tinh dày 0,635 mm lớp 2"),
    ("mài vệ sinh ngoài vùng", "mài vệ sinh trong vùng quét epoxy", "trám phẳng ngoài vùng", "trám phẳng sumendur80 bằng 5%"),
    ("hệ sơn bảo vệ", "sơn bảo vệ", "quét epoxy hm-180c3p hoặc tương đương bảo vệ dầm", "quét epoxy bảo vệ"),
    ("vận chuyển đổ thải", "bao tải"),
)


def ordered_stage(kind, name, position):
    normalized = name.casefold().strip()
    if normalized.startswith(JACKET_SOURCE):
        name = JACKET_LABEL
        normalized = name.casefold()
    phases = PILE_PHASES if kind == "pile" else BEAM_PHASES
    for phase, steps in enumerate(phases, start=1):
        for step, prefix in enumerate(steps):
            if normalized.startswith(prefix):
                # Keep the original THKL row order inside an equivalent step.
                return name, phase * 1000 + step * 100 + position % 100
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    uri = args.database.resolve().as_uri() + ("?mode=rw" if args.apply else "?mode=ro")
    with closing(sqlite3.connect(uri, uri=True)) as db, db:
        if args.apply:
            db.execute("BEGIN IMMEDIATE")
        projects = db.execute(
            "SELECT DISTINCT project_id FROM component_stage_definitions WHERE code LIKE 'DAP-%'"
        ).fetchall()
        if len(projects) != 1:
            parser.exit(1, f"Expected one project with DAP stages, found {len(projects)}\n")
        project, = projects[0]
        changes = []
        unknown = set()
        for sid, kind, name, position in db.execute(
            """SELECT id, component_type, name, position FROM component_stage_definitions
               WHERE project_id = ? AND code LIKE 'DAP-%' AND component_type IN ('pile', 'beam')""",
            (project,),
        ):
            new = ordered_stage(kind, name, position)
            if new is None:
                unknown.add(f"{kind}: {name}")
            elif new != (name, position):
                changes.append((sid, name, position, *new))
        if unknown:
            parser.exit(1, "Unmapped DAP stages:\n" + "\n".join(sorted(unknown)) + "\n")
        print(f"{len(changes)} stage definitions to update ({'apply' if args.apply else 'preview'})")
        if not args.apply or not changes:
            return
        actor, = db.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY username LIMIT 1").fetchone()
        db.executemany(
            "UPDATE component_stage_definitions SET name=?, position=? WHERE id=?",
            [(label, position, sid) for sid, _, _, label, position in changes],
        )
        db.execute(
            """INSERT INTO audit_logs (id, project_id, actor_id, action, entity, entity_id, detail, at)
               VALUES (?, ?, ?, 'stage_sequence_updated', 'Project', ?, ?, ?)""",
            (str(uuid4()), project, actor, project, json.dumps(changes, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat()),
        )


if __name__ == "__main__":
    main()
