import io
import sqlite3
import tarfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.backup import backup
from scripts.restore import restore


def test_backup_restores_database_and_original(tmp_path):
    data = tmp_path / "data"
    (data / "storage" / "project").mkdir(parents=True)
    (data / "storage" / "project" / "original.jpg").write_bytes(b"original")
    with sqlite3.connect(data / "app.db") as db:
        db.execute("create table sample (value text)")
        db.execute("insert into sample values ('saved')")
    archive = tmp_path / "backup.tar.gz"
    backup(data, archive)
    if sys.platform != "win32":
        # Windows has no POSIX mode bits; chmod only toggles the read-only flag.
        assert archive.stat().st_mode & 0o777 == 0o600
    target = tmp_path / "restored"
    restore(archive, target)
    with sqlite3.connect(target / "app.db") as db:
        assert db.execute("select value from sample").fetchone() == ("saved",)
    assert (target / "storage" / "project" / "original.jpg").read_bytes() == b"original"
    if sys.platform != "win32":
        assert (target / "storage" / "project" / "original.jpg").stat().st_mode & 0o777 == 0o600
    try:
        restore(archive, target)
    except FileExistsError:
        pass
    else:
        assert False, "restore must not overwrite existing data"


def test_restore_rejects_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("../outside.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    try:
        restore(archive, tmp_path / "target")
    except ValueError:
        pass
    else:
        assert False, "unsafe archive path was accepted"


def test_backup_rejects_archive_inside_source_tree(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "app.db") as db:
        db.execute("create table sample (value text)")
    try:
        backup(data, data / "storage" / "self.tar.gz")
    except ValueError:
        pass
    else:
        assert False, "backup must not archive its own output"
