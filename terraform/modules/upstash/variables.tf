variable "database_name" {
  type = string
}

variable "region" {
  type = string
}

variable "tls" {
  type    = string
  default = "true"
}

variable "multi_zone" {
  type    = string
  default = "false"
}
