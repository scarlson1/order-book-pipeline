variable "cluster_name" {
  type = string
}

variable "cloud_provider" {
  type    = string
  default = "GCP"
}

variable "region" {
  type = string
}

variable "delete_protection" {
  type    = bool
  default = false
}
