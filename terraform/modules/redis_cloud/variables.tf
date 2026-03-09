variable "subscription_name" {
  type    = string
  default = "orderbook-pipeline"
}

variable "database_name" {
  type = string
}

variable "region" {
  type        = string
  description = "AWS/GCP region matching your OCI VM location"
  default = "us-central1"
}

variable "cloud_provider" {
  type    = string
  default = "GCP"
}

variable "memory_limit_mb" {
  type    = number
  default = 30
  description = "Memory in MB (30MB on free tier)"
}

variable "password" {
  type      = string
  sensitive = true
}

variable "tls" {
  type    = bool
  default = true
}

variable "subscription_id" {
  type        = string
  description = "Existing Redis Cloud subscription ID"
  default     = "3148705"
}