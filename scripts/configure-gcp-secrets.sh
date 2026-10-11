#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"

declare -A secret_values=(
  [github-token]="${GH_TOKEN:-}"
  [neatlogs-api-key]="${NEATLOGS_API_KEY:-}"
  [openai-api-key]="${OPENAI_API_KEY:-}"
  [promise-ledger-azure-api-key]="${PROMISE_LEDGER_AZURE_API_KEY:-}"
  [promise-ledger-azure-api-version]="${PROMISE_LEDGER_AZURE_API_VERSION:-}"
  [promise-ledger-azure-deployment]="${PROMISE_LEDGER_AZURE_DEPLOYMENT:-}"
  [promise-ledger-azure-endpoint]="${PROMISE_LEDGER_AZURE_ENDPOINT:-}"
)

for secret_id in "${!secret_values[@]}"; do
  value="${secret_values[$secret_id]}"
  if [[ -z "${value}" ]]; then
    echo "Missing value for ${secret_id}" >&2
    exit 2
  fi
  printf '%s' "${value}" | gcloud secrets versions add "${secret_id}" \
    --project "${GCP_PROJECT_ID}" \
    --data-file=- >/dev/null
  echo "Added a new version for ${secret_id}"
done

