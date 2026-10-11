#!/usr/bin/env bash
set -euo pipefail

base_url="${PROMISE_LEDGER_URL:-https://promise-ledger.onrender.com}"
trigger_token="${PROMISE_LEDGER_TRIGGER_TOKEN:-}"
if [[ -z "${trigger_token}" ]] && command -v security >/dev/null 2>&1; then
  trigger_token="$(
    security find-generic-password \
      -a kkhushal1531@gmail.com \
      -s promise-ledger-render-trigger \
      -w
  )"
fi
if [[ -z "${trigger_token}" ]]; then
  echo "Set PROMISE_LEDGER_TRIGGER_TOKEN or add promise-ledger-render-trigger to Keychain." >&2
  exit 2
fi

start_response="$(curl -fsS --config - <<EOF
url = "${base_url}/api/agent-runs"
request = "POST"
header = "Authorization: Bearer ${trigger_token}"
EOF
)"
echo "Started autonomous run: ${start_response}"

while true; do
  status_response="$(curl -fsS --config - <<EOF
url = "${base_url}/api/agent-runs/status"
header = "Authorization: Bearer ${trigger_token}"
EOF
)"
  run_status="$(
    printf '%s' "${status_response}" \
      | sed -n 's/.*"status":"\([^"]*\)".*/\1/p'
  )"
  echo "Render status: ${run_status:-unknown}"
  case "${run_status}" in
    completed)
      exit 0
      ;;
    failed)
      echo "${status_response}" >&2
      exit 1
      ;;
  esac
  sleep 5
done
