#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Create .venv and install backend/requirements.txt first" >&2
  exit 1
fi
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Run npm install in frontend first" >&2
  exit 1
fi
cd "$ROOT/backend"
mkdir -p "$ROOT/data/storage/site" "$ROOT/data/storage/engineering-ai" "$ROOT/data/storage/acceptance"
chmod 700 "$ROOT/data/storage" "$ROOT/data/storage/site" "$ROOT/data/storage/engineering-ai" "$ROOT/data/storage/acceptance"
export SITE_REPORT_STORAGE="$ROOT/data/storage/site"
export ENGINEERING_AI_STORAGE="$ROOT/data/storage/engineering-ai"
export ACCEPTANCE_STORAGE="$ROOT/data/storage/acceptance"
export ACCEPTANCE_TEMPLATE="$ROOT/data/templates/acceptance-original.xlsx"
export ENGINEERING_AI_MAX_PDF_BYTES="${ENGINEERING_AI_MAX_PDF_BYTES:-80000000}"
export ENGINEERING_AI_PROVIDER="${ENGINEERING_AI_PROVIDER:-opencode_deepseek}"
export ENGINEERING_AI_OPENCODE_MODEL="${ENGINEERING_AI_OPENCODE_MODEL:-opencode-go/deepseek-v4.1-flash}"
export ENGINEERING_AI_TIMEOUT="${ENGINEERING_AI_TIMEOUT:-180}"
if [[ -z "${TESSDATA_PREFIX:-}" && -f "$HOME/.local/share/tessdata/vie.traineddata" ]]; then
  export TESSDATA_PREFIX="$HOME/.local/share/tessdata"
fi
export CONSTRUCTION_API_PORT="${CONSTRUCTION_API_PORT:-8765}"
"$ROOT/.venv/bin/alembic" upgrade head
PYTHONPATH="$ROOT/backend" "$ROOT/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$CONSTRUCTION_API_PORT" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
cd "$ROOT/frontend"
npm run dev
