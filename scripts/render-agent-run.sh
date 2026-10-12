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
  PROMISE_LEDGER_AZURE_REASONING_EFFORT
  NEATLOGS_API_KEY
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 2
  fi
done

# Render already isolates this disposable container and per-run Git worktree. Codex's
# nested bubblewrap sandbox is unavailable there, so bypass only the inner sandbox.
export PROMISE_LEDGER_CODEX_EXTERNAL_SANDBOX=true

workspace="${PROMISE_LEDGER_WORKSPACE:-/tmp/promise-ledger-runs}"
mkdir -p "${workspace}"
run_id="${PROMISE_LEDGER_RUN_ID}"
run_root="${workspace%/}/${run_id}"
target="${run_root}/tasklane-demo"
contract_root="${target}/contracts"
registry="${contract_root}/id_registry.json"
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

mapfile -t documents < <(ledger list-contracts --directory "${contract_root}")
if [[ "${#documents[@]}" -eq 0 ]]; then
  echo "No contract documents found in ${contract_root}" >&2
  exit 2
fi
if [[ ! -f "${registry}" ]]; then
  echo "Contract registry not found: ${registry}" >&2
  exit 2
fi
document_arguments=()
for document in "${documents[@]}"; do
  document_arguments+=(--document "${document}")
done

exec ledger agent-run \
  --target "${target}" \
  --database "${target_database}" \
  "${document_arguments[@]}" \
  --registry "${registry}" \
  --repository "${TARGET_REPOSITORY}" \
  --state-database "${PROMISE_LEDGER_STATE_DATABASE}" \
  --worktree-root "${worktrees}" \
  --output "${output}" \
  --run-id "${run_id}"
