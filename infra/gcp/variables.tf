variable "project_id" {
  description = "Dedicated GCP project linked to the hackathon billing account."
  type        = string
}

variable "region" {
  description = "GCP region for all regional resources."
  type        = string
  default     = "asia-south1"
}

variable "billing_account_id" {
  description = "Billing account used for the budget alert."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly budget alert amount in USD."
  type        = number
  default     = 250
}

variable "database_tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-f1-micro"
}

