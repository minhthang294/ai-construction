"""Restore a backup into a new, empty directory for manual cutover."""

import argparse
import shutil
import tarfile
from pathlib import Path


def restore(archive_path: Path, target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise FileExistsError("Restore target must be empty")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            path = Path(member.name)
            if not path.parts or path.is_absolute() or ".." in path.parts or path.parts[0] not in {"app.db", "storage", "templates"} or (path.parts[0] == "app.db" and len(path.parts) != 1):
                raise ValueError("Unsafe archive path")
            if not (member.isfile() or member.isdir()):
                raise ValueError("Archive contains unsupported link or device")
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.chmod(0o700)
        for member in members:
            destination = target / member.name
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                destination.chmod(0o700)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("Archive file missing data")
                with source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output)
                destination.chmod(0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    restore(args.archive, args.target)
