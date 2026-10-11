#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCP_BILLING_ACCOUNT_ID:?Set GCP_BILLING_ACCOUNT_ID}"
export GCP_PROJECT_ID

region="${GCP_REGION:-asia-south1}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_root="${TASKLANE_REPOSITORY_PATH:-${repo_root}/../tasklane-demo}"
state_bucket="${GCP_PROJECT_ID}-promise-ledger-tfstate"
registry="${region}-docker.pkg.dev/${GCP_PROJECT_ID}/promise-ledger"
promise_image="${registry}/promise-ledger:$(git -C "${repo_root}" rev-parse --short HEAD)"
tasklane_image="${registry}/tasklane-demo:$(git -C "${target_root}" rev-parse --short HEAD)"

for command in gcloud terraform git; do
  command -v "${command}" >/dev/null || { echo "Missing required command: ${command}" >&2; exit 2; }
done

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null
if ! gcloud storage buckets describe "gs://${state_bucket}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${state_bucket}" \
    --location="${region}" \
    --uniform-bucket-level-access
  gcloud storage buckets update "gs://${state_bucket}" --versioning
fi

terraform -chdir="${repo_root}/infra/gcp" init -reconfigure \
  -backend-config="bucket=${state_bucket}"
terraform -chdir="${repo_root}/infra/gcp" apply -auto-approve \
  -var="project_id=${GCP_PROJECT_ID}" \
  -var="billing_account_id=${GCP_BILLING_ACCOUNT_ID}" \
  -var="region=${region}"

runtime_sa="$(terraform -chdir="${repo_root}/infra/gcp" output -raw runtime_service_account)"
scheduler_sa="$(terraform -chdir="${repo_root}/infra/gcp" output -raw scheduler_service_account)"
sql_connection="$(terraform -chdir="${repo_root}/infra/gcp" output -raw cloud_sql_connection_name)"

"${repo_root}/scripts/configure-gcp-secrets.sh"

gcloud builds submit "${repo_root}" \
  --config="${repo_root}/cloudbuild.yaml" \
  --substitutions="_IMAGE=${promise_image}"
gcloud builds submit "${target_root}" --tag "${tasklane_image}"

gcloud run deploy tasklane-demo \
  --project="${GCP_PROJECT_ID}" \
  --region="${region}" \
  --image="${tasklane_image}" \
  --service-account="${runtime_sa}" \
  --add-cloudsql-instances="${sql_connection}" \
  --set-secrets="DATABASE_URL=tasklane-database-url:latest" \
  --min=0 --max=2 --cpu=1 --memory=512Mi \
  --allow-unauthenticated --quiet

gcloud run deploy promise-ledger \
  --project="${GCP_PROJECT_ID}" \
  --region="${region}" \
  --image="${promise_image}" \
  --service-account="${runtime_sa}" \
  --add-cloudsql-instances="${sql_connection}" \
  --set-secrets="PROMISE_LEDGER_STATE_DATABASE=promise-ledger-state-database:latest" \
  --min=0 --max=2 --cpu=1 --memory=512Mi \
  --allow-unauthenticated --quiet

gcloud run jobs deploy promise-ledger-agent \
  --project="${GCP_PROJECT_ID}" \
  --region="${region}" \
  --image="${promise_image}" \
  --service-account="${runtime_sa}" \
  --add-cloudsql-instances="${sql_connection}" \
  --command="/app/scripts/cloud-agent-run.sh" \
  --set-env-vars="TARGET_REPOSITORY=khushalkumar/tasklane-demo" \
  --set-secrets="TARGET_DATABASE_URL=tasklane-database-url:latest,PROMISE_LEDGER_STATE_DATABASE=promise-ledger-state-database:latest,GH_TOKEN=github-token:latest,OPENAI_API_KEY=openai-api-key:latest,NEATLOGS_API_KEY=neatlogs-api-key:latest,PROMISE_LEDGER_AZURE_ENDPOINT=promise-ledger-azure-endpoint:latest,PROMISE_LEDGER_AZURE_API_KEY=promise-ledger-azure-api-key:latest,PROMISE_LEDGER_AZURE_DEPLOYMENT=promise-ledger-azure-deployment:latest,PROMISE_LEDGER_AZURE_API_VERSION=promise-ledger-azure-api-version:latest" \
  --cpu=2 --memory=2Gi --task-timeout=3600s --max-retries=1 --quiet

job_uri="https://run.googleapis.com/v2/projects/${GCP_PROJECT_ID}/locations/${region}/jobs/promise-ledger-agent:run"
if gcloud scheduler jobs describe promise-ledger-nightly --location="${region}" >/dev/null 2>&1; then
  scheduler_action=update
else
  scheduler_action=create
fi
gcloud scheduler jobs "${scheduler_action}" http promise-ledger-nightly \
  --location="${region}" \
  --schedule="0 1 * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="${job_uri}" \
  --http-method=POST \
  --oauth-service-account-email="${scheduler_sa}" \
  --quiet

gcloud run jobs execute promise-ledger-agent \
  --project="${GCP_PROJECT_ID}" \
  --region="${region}" \
  --wait

gcloud run services describe promise-ledger \
  --project="${GCP_PROJECT_ID}" \
  --region="${region}" \
  --format='value(status.url)'
