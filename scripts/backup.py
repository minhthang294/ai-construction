"""Consistent SQLite backup plus original private files and template copies."""

import argparse
import sqlite3
import tarfile
import tempfile
from pathlib import Path


def backup(data_dir: Path, output: Path) -> None:
    database = data_dir / "app.db"
    if not database.is_file():
        raise FileNotFoundError(database)
    if output.resolve().is_relative_to(data_dir.resolve()):
        raise ValueError("Backup archive must be outside the data directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / "app.db"
        with sqlite3.connect(database) as source, sqlite3.connect(snapshot) as destination:
            source.backup(destination)
        with output.open("xb") as stream:
            output.chmod(0o600)
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                archive.add(snapshot, arcname="app.db")
                for name in ("storage", "templates"):
                    path = data_dir / name
                    if path.exists():
                        archive.add(path, arcname=name, recursive=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    backup(args.data_dir, args.output)
