# GCP production deployment

This deployment is automated. Do not create service-account JSON keys and do not put provider
keys in Terraform variables, GitHub, or shell history. Runtime credentials are versioned in
Secret Manager and mounted directly into Cloud Run.

## What Khushal needs from the GCP owner

The GCP owner must do these account-level steps because they control the billing account:

1. Create a dedicated project and link the friend's $300-credit billing account.
2. Grant `kkhushal1531@gmail.com` the project roles below.
3. Grant the same email **Billing Account Costs Manager** on the linked billing account so
   Terraform can create the $250 budget alert.
4. Send Khushal only the project id and billing account id. Never send a password or service
   account key file.

Required project roles:

- Artifact Registry Administrator
- Cloud Build Editor
- Cloud Run Admin
- Cloud Scheduler Admin
- Cloud SQL Admin
- Project IAM Admin
- Secret Manager Admin
- Service Account Admin
- Service Account User
- Service Usage Admin
- Storage Admin

These roles are needed for the first deployment. After deployment, Project IAM Admin, Service
Account Admin, Service Usage Admin, and Storage Admin can be removed until infrastructure changes
again. The Cloud Run runtime receives only Cloud SQL client, Secret Manager accessor, and log
writer permissions.

## Local prerequisites

Install the Google Cloud CLI and Terraform, then authenticate in the browser:

```bash
gcloud auth login kkhushal1531@gmail.com
gcloud auth application-default login
```

Set deployment inputs without printing their values:

```bash
export GCP_PROJECT_ID="the-dedicated-project-id"
export GCP_BILLING_ACCOUNT_ID="000000-000000-000000"
export GCP_REGION="asia-south1"

export GH_TOKEN="$(gh auth token)"
export NEATLOGS_API_KEY="..."
export OPENAI_API_KEY="..."
export PROMISE_LEDGER_AZURE_ENDPOINT="..."
export PROMISE_LEDGER_AZURE_API_KEY="..."
export PROMISE_LEDGER_AZURE_DEPLOYMENT="..."
export PROMISE_LEDGER_AZURE_API_VERSION="..."
```

The deploy script never echoes secret values. It creates new Secret Manager versions by piping
values over standard input.

## Deploy and prove the system

From the Promise Ledger repository:

```bash
./scripts/deploy-gcp.sh
```

The script performs the complete sequence:

1. Creates a versioned GCS Terraform-state bucket.
2. Applies Artifact Registry, Cloud SQL PostgreSQL 16, two databases/users, service accounts,
   Secret Manager resources, least-privilege runtime IAM, and a $250 billing budget.
3. Uploads provider and GitHub credentials as Secret Manager versions.
4. Builds Promise Ledger and Tasklane with Cloud Build.
5. Deploys the Tasklane API and Promise Ledger UI to Cloud Run.
6. Deploys the autonomous Promise Ledger Cloud Run Job.
7. Creates a 1:00 AM Asia/Kolkata daily Cloud Scheduler trigger.
8. Executes the job once and waits for completion.
9. Prints the hosted Promise Ledger URL.

The job clones the private `khushalkumar/tasklane-demo` repository, seeds Cloud SQL, extracts the
three contracts, compiles and runs checks, investigates safe violations with Entire, creates or
reuses normal GitHub PRs, rechecks their combined commits, and persists the final ledger in the
Promise Ledger Cloud SQL database. The UI reads that latest durable final result directly.

## Cost and safety controls

- One zonal `db-f1-micro` PostgreSQL instance hosts separate `tasklane` and `promise_ledger`
  databases.
- Cloud Run services scale from zero and are capped at two instances.
- The agent job is capped at 2 vCPU, 2 GiB, one task, a 60-minute timeout, and one retry.
- A $250 monthly budget sends standard Cloud Billing notifications at 50%, 80%, and 100%.
- Cloud SQL has seven retained backups and seven days of point-in-time recovery.
- Cloud SQL deletion protection is enabled.
- P-021 data residency remains a human-controlled alert; the job does not migrate data or open a
  migration PR.

