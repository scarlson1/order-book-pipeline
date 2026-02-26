variable "resource_group_name" {
  type = string
}

variable "cluster_name" {
  type = string
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
