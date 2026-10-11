locals {
  services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
  ])
  runtime_secret_ids = toset([
    "github-token",
    "neatlogs-api-key",
    "openai-api-key",
    "promise-ledger-azure-api-key",
    "promise-ledger-azure-api-version",
    "promise-ledger-azure-deployment",
    "promise-ledger-azure-endpoint",
  ])
}

resource "google_project_service" "required" {
  for_each           = local.services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "promise-ledger"
  description   = "Promise Ledger and Tasklane container images"
  format        = "DOCKER"
  depends_on    = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  account_id   = "promise-ledger-runtime"
  display_name = "Promise Ledger Cloud Run runtime"
}

resource "google_service_account" "scheduler" {
  account_id   = "promise-ledger-scheduler"
  display_name = "Promise Ledger scheduled job invoker"
}

resource "google_project_iam_member" "runtime_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "scheduler_run" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_project_iam_member" "cloud_build_artifacts" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "cloud_build_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

resource "google_sql_database_instance" "postgres" {
  name                = "promise-ledger-postgres"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = true

  settings {
    tier              = var.database_tier
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 10
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "02:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    maintenance_window {
      day          = 7
      hour         = 3
      update_track = "stable"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_sql_database" "tasklane" {
  name     = "tasklane"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_database" "promise_ledger" {
  name     = "promise_ledger"
  instance = google_sql_database_instance.postgres.name
}

resource "random_password" "tasklane" {
  length  = 32
  special = false
}

resource "random_password" "promise_ledger" {
  length  = 32
  special = false
}

resource "google_sql_user" "tasklane" {
  name     = "tasklane"
  instance = google_sql_database_instance.postgres.name
  password = random_password.tasklane.result
}

resource "google_sql_user" "promise_ledger" {
  name     = "promise_ledger"
  instance = google_sql_database_instance.postgres.name
  password = random_password.promise_ledger.result
}

resource "google_secret_manager_secret" "runtime" {
  for_each  = local.runtime_secret_ids
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "tasklane_database_url" {
  secret_id = "tasklane-database-url"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "tasklane_database_url" {
  secret      = google_secret_manager_secret.tasklane_database_url.id
  secret_data = "postgresql+psycopg://tasklane:${random_password.tasklane.result}@/tasklane?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"
}

resource "google_secret_manager_secret" "state_database_url" {
  secret_id = "promise-ledger-state-database"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "state_database_url" {
  secret      = google_secret_manager_secret.state_database_url.id
  secret_data = "postgresql+psycopg://promise_ledger:${random_password.promise_ledger.result}@/promise_ledger?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"
}

resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = setunion(local.runtime_secret_ids, toset(["tasklane-database-url", "promise-ledger-state-database"]))
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
  depends_on = [
    google_secret_manager_secret.runtime,
    google_secret_manager_secret.tasklane_database_url,
    google_secret_manager_secret.state_database_url,
  ]
}

resource "google_billing_budget" "credits_guardrail" {
  billing_account = var.billing_account_id
  display_name    = "Promise Ledger ${var.project_id} budget"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  dynamic "threshold_rules" {
    for_each = toset([0.5, 0.8, 1.0])
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }
}

data "google_project" "current" {
  project_id = var.project_id
}
