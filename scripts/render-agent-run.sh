#!/usr/bin/env bash
set -euo pipefail

required=(
  PROMISE_LEDGER_RUN_ID
  TARGET_REPOSITORY
  PROMISE_LEDGER_STATE_DATABASE
  GH_TOKEN
  PROMISE_LEDGER_AZURE_ENDPOINT
  PROMISE_LEDGER_AZURE_API_KEY
  PROMISE_LEDGER_AZURE_DEPLOYMENT
  PROMISE_LEDGER_AZURE_API_VERSION
  NEATLOGS_API_KEY
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 2
  fi
done

workspace="${PROMISE_LEDGER_WORKSPACE:-/tmp/promise-ledger-runs}"
mkdir -p "${workspace}"
run_id="${PROMISE_LEDGER_RUN_ID}"
run_root="${workspace%/}/${run_id}"
target="${run_root}/tasklane-demo"
worktrees="${run_root}/worktrees"
output="${run_root}/run-autonomous.json"
target_database="${run_root}/tasklane.db"

if [[ -e "${run_root}" ]]; then
  echo "Run workspace already exists: ${run_root}" >&2
  exit 2
fi
mkdir -p "${run_root}"

gh auth setup-git
gh repo clone "${TARGET_REPOSITORY}" "${target}" -- --depth=100
uv run --project "${target}" tasklane-seed "${target_database}"

exec ledger agent-run \
  --target "${target}" \
  --database "${target_database}" \
  --document /app/contracts/Northwind_DPA_v3.pdf \
  --document /app/contracts/Acme_MSA_2026.pdf \
  --document /app/contracts/privacy_policy.md \
  --registry /app/contracts/id_registry.json \
  --repository "${TARGET_REPOSITORY}" \
  --state-database "${PROMISE_LEDGER_STATE_DATABASE}" \
  --worktree-root "${worktrees}" \
  --output "${output}" \
  --run-id "${run_id}"
