#!/usr/bin/env bash
# Run every automated gate against temporary databases and storage.
# Never reads or writes data/app.db or the user's source workbook.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$(mktemp -d /tmp/opencode/verify.XXXXXX)"
export DATABASE_URL="sqlite:///$RUN_DIR/app.db"
export SITE_REPORT_STORAGE="$RUN_DIR/storage/site"
export ENGINEERING_AI_STORAGE="$RUN_DIR/storage/engineering-ai"
export ACCEPTANCE_STORAGE="$RUN_DIR/storage/acceptance"
mkdir -p "$SITE_REPORT_STORAGE" "$ENGINEERING_AI_STORAGE" "$ACCEPTANCE_STORAGE"

STATUS=0

echo "== Backend tests (temporary DB: $DATABASE_URL) =="
( cd "$ROOT/backend" && "$ROOT/.venv/bin/python" -m pytest tests -q )
BACKEND_STATUS=$?
[ "$BACKEND_STATUS" -eq 0 ] || STATUS=1

echo
echo "== Frontend tests =="
( cd "$ROOT/frontend" && npm test )
FRONTEND_TEST_STATUS=$?
[ "$FRONTEND_TEST_STATUS" -eq 0 ] || STATUS=1

echo
echo "== Frontend production build =="
( cd "$ROOT/frontend" && npm run build )
FRONTEND_BUILD_STATUS=$?
[ "$FRONTEND_BUILD_STATUS" -eq 0 ] || STATUS=1

echo
echo "== Summary =="
echo "backend tests:     $([ "$BACKEND_STATUS" -eq 0 ] && echo PASS || echo FAIL)"
echo "frontend tests:    $([ "$FRONTEND_TEST_STATUS" -eq 0 ] && echo PASS || echo FAIL)"
echo "frontend build:    $([ "$FRONTEND_BUILD_STATUS" -eq 0 ] && echo PASS || echo FAIL)"
echo "artifacts kept in: $RUN_DIR"

exit "$STATUS"
