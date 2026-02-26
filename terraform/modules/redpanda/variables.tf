variable "resource_group_name" {
  type = string
}

variable "existing_resource_group_id" {
  type    = string
  default = null
}

variable "cluster_name" {
  type = string
}

variable "existing_cluster_id" {
  type    = string
  default = null
}

variable "serverless_region" {
  type = string
}

variable "kafka_user" {
  type = string
}

variable "kafka_password" {
  type      = string
  sensitive = true
}

variable "kafka_mechanism" {
  type    = string
  default = "scram-sha-256"
}

variable "topic_prefix" {
  type    = string
  default = "orderbook"
}
