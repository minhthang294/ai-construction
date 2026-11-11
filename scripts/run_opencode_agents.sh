#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p docs/agent-reports/logs
NAMES=(site-report-agent engineering-ai-agent acceptance-agent)
PROMPTS=(
  "Implement Site Report according to docs/API_CONTRACTS.md and docs/AGENT_BOUNDARIES.md"
  "Implement Engineering AI according to docs/AI_ARCHITECTURE.md and docs/API_CONTRACTS.md"
  "Implement Acceptance according to docs/API_CONTRACTS.md and docs/AGENT_BOUNDARIES.md"
)
DIRS=("$ROOT" "$ROOT" "$ROOT")

if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [[ -z "$(git status --porcelain)" ]]; then
  RUN_ID="$(date +%Y%m%d%H%M%S)"
  BRANCHES=(site-report engineering-ai acceptance)
  for index in 0 1 2; do
    DIRS[$index]="$ROOT/.worktrees/${BRANCHES[$index]}"
    git worktree add -b "opencode/${BRANCHES[$index]}-$RUN_ID" "${DIRS[$index]}" HEAD
  done
  PIDS=()
  for index in 0 1 2; do
    (cd "${DIRS[$index]}" && opencode run --model opencode-go/deepseek-v4.1-flash \
      --agent "${NAMES[$index]}" --format json "${PROMPTS[$index]}") \
      > "$ROOT/docs/agent-reports/logs/${NAMES[$index]}.jsonl" &
    PIDS+=("$!")
  done
  FAILED=0
  for pid in "${PIDS[@]}"; do wait "$pid" || FAILED=1; done
  exit "$FAILED"
fi

# Without a clean Git checkout, shared-directory agents run one at a time.
for index in 0 1 2; do
  opencode run --model opencode-go/deepseek-v4.1-flash \
    --agent "${NAMES[$index]}" --format json "${PROMPTS[$index]}" \
    > "$ROOT/docs/agent-reports/logs/${NAMES[$index]}.jsonl"
done
