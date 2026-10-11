output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "cloud_sql_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "scheduler_service_account" {
  value = google_service_account.scheduler.email
}

