variable "project_name" {
  type    = string
  default = "orderbook-pipeline"
}

# OCI
variable "oci_tenancy_ocid" { type = string }
variable "oci_user_ocid" { type = string }
variable "oci_fingerprint" { type = string }
variable "oci_private_key_path" { type = string }
variable "oci_region" { type = string }
variable "oci_compartment_ocid" { type = string }
variable "oci_ad_index" {
  type    = number
  default = 1
}
variable "oci_admin_cidr" { type = string }
variable "oci_vm_shape" {
  type    = string
  default = "VM.Standard.A1.Flex"
}
variable "oci_vm_ocpus" {
  type    = number
  default = 2
}
variable "oci_vm_memory_gb" {
  type    = number
  default = 12
}
variable "oci_boot_volume_gb" {
  type    = number
  default = 100
}
variable "oci_ssh_public_key" { type = string }

# CockroachDB
variable "cockroach_api_key" {
  type      = string
  sensitive = true
}
variable "cockroach_cluster_name" {
  type    = string
  default = "trading-pipeline"
}
variable "cockroach_cloud_provider" {
  type    = string
  default = "GCP"
}
variable "cockroach_region" {
  type    = string
  default = "us-central1"
}
variable "cockroach_delete_protection" {
  type    = bool
  default = false
}

# Upstash
variable "upstash_email" { type = string }
variable "upstash_api_key" {
  type      = string
  sensitive = true
}
variable "upstash_region" {
  type    = string
  default = "us-central1"
}

# Redpanda Cloud
variable "redpanda_client_id" {
  type      = string
  sensitive = true
}
variable "redpanda_client_secret" {
  type      = string
  sensitive = true
}
variable "redpanda_resource_group_name" {
  type    = string
  default = "default"
}
variable "redpanda_existing_resource_group_id" {
  type    = string
  default = null
}
variable "redpanda_cluster_name" {
  type    = string
  default = "orderbook"
}
variable "redpanda_existing_cluster_id" {
  type    = string
  default = null
}
variable "redpanda_serverless_region" {
  type    = string
  default = "us-central1"
}
variable "redpanda_kafka_user" {
  type    = string
  default = "orderbook_user"
}
variable "redpanda_kafka_password" {
  type      = string
  sensitive = true
}
variable "redpanda_topic_prefix" {
  type    = string
  default = "orderbook"
}
