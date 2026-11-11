#!/usr/bin/env bash
# Create the first admin interactively. The password is never written to
# shell history, source, or a command-line argument.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Create .venv and install backend/requirements.txt first" >&2
  exit 1
fi

PYTHONPATH="$ROOT/backend" "$ROOT/.venv/bin/python" - <<'PY'
import getpass
import os

from app.core.bootstrap import main

username = input("Admin username: ").strip()
if not username:
    raise SystemExit("Username is required")
password = getpass.getpass("Admin password (12+ characters): ")
confirm = getpass.getpass("Confirm password: ")
if password != confirm:
    raise SystemExit("Passwords do not match")
if len(password) < 12:
    raise SystemExit("Password must be at least 12 characters")
os.environ["BOOTSTRAP_ADMIN_USER"] = username
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = password
main()
PY
