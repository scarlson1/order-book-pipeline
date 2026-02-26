variable "project_name" {
  type = string
}

variable "tenancy_ocid" {
  type = string
}

variable "compartment_ocid" {
  type = string
}

variable "ad_index" {
  type    = number
  default = 0
}

variable "admin_cidr" {
  type = string
}

variable "vm_shape" {
  type    = string
  default = "VM.Standard.A1.Flex"
}

variable "vm_ocpus" {
  type    = number
  default = 2
}

variable "vm_memory_gb" {
  type    = number
  default = 12
}

variable "boot_volume_gb" {
  type    = number
  default = 100
}

variable "ssh_public_key" {
  type = string
}
