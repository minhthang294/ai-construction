#!/usr/bin/env bash
# Copy the user's current PYC/BBNT workbook into the canonical template used
# by the app. Refuses to run while LibreOffice has the workbook open.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-/home/thangpham/Downloads/YCNT và BBNT.19.10 - nt thuc te.xlsx}"
DEST="$ROOT/data/templates/acceptance-original.xlsx"
ARCHIVE="$ROOT/data/templates/archive"
LOCK="$(dirname "$SRC")/.~lock.$(basename "$SRC")#"

if [[ ! -f "$SRC" ]]; then
  echo "Source workbook not found: $SRC" >&2
  exit 1
fi
if [[ -e "$LOCK" ]]; then
  echo "Workbook is open in LibreOffice (lock file exists): $LOCK" >&2
  echo "Save, close LibreOffice, then run this script again." >&2
  exit 2
fi

TMP="$(mktemp /tmp/opencode/acceptance-template.XXXXXX.xlsx)"
trap 'rm -f "$TMP"' EXIT
cp -- "$SRC" "$TMP"

PYTHONPATH="$ROOT/backend" "$ROOT/.venv/bin/python" - "$TMP" <<'PY'
import sys
from pathlib import Path
from app.acceptance.template import validate_template

path = Path(sys.argv[1])
validate_template(path)
print("Template validation: OK")
PY

mkdir -p "$ARCHIVE"
chmod 700 "$ARCHIVE"
if [[ -f "$DEST" ]]; then
  OLD_SHA="$(sha256sum "$DEST" | cut -d' ' -f1)"
  cp -p "$DEST" "$ARCHIVE/acceptance-original-$OLD_SHA.xlsx"
  chmod 600 "$ARCHIVE/acceptance-original-$OLD_SHA.xlsx"
fi

install -m 600 "$TMP" "$DEST"
NEW_SHA="$(sha256sum "$DEST" | cut -d' ' -f1)"
echo "Updated: $DEST"
echo "SHA-256: $NEW_SHA"
echo "Previous version archived in: $ARCHIVE"
