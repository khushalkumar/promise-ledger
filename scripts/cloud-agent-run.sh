#!/usr/bin/env bash
set -euo pipefail

required=(
  TARGET_REPOSITORY
  TARGET_DATABASE_URL
  PROMISE_LEDGER_STATE_DATABASE
  GH_TOKEN
  OPENAI_API_KEY
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

workspace="${PROMISE_LEDGER_WORKSPACE:-/workspace}"
mkdir -p "${workspace}"
run_root="$(mktemp -d "${workspace%/}/run.XXXXXX")"
target="${run_root}/tasklane-demo"
worktrees="${run_root}/worktrees"
output="${run_root}/run-autonomous.json"

gh auth setup-git
gh repo clone "${TARGET_REPOSITORY}" "${target}" -- --depth=100

uv run --project "${target}" tasklane-seed "${TARGET_DATABASE_URL}"

exec ledger agent-run \
  --target "${target}" \
  --database "${TARGET_DATABASE_URL}" \
  --document /app/contracts/Northwind_DPA_v3.pdf \
  --document /app/contracts/Acme_MSA_2026.pdf \
  --document /app/contracts/privacy_policy.md \
  --registry /app/contracts/id_registry.json \
  --repository "${TARGET_REPOSITORY}" \
  --state-database "${PROMISE_LEDGER_STATE_DATABASE}" \
  --worktree-root "${worktrees}" \
  --output "${output}"
