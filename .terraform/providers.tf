terraform {
  required_version = ">= 1.6.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
    cockroach = {
      source  = "cockroachdb/cockroach"
      version = "~> 1.13"
    }
    upstash = {
      source  = "upstash/upstash"
      version = "~> 1.8"
    }
    redpanda = {
      source  = "redpanda-data/redpanda"
      version = "~> 1.0"
    }
  }
}

provider "oci" {
  tenancy_ocid     = var.oci_tenancy_ocid
  user_ocid        = var.oci_user_ocid
  fingerprint      = var.oci_fingerprint
  private_key_path = var.oci_private_key_path
  region           = var.oci_region
}

provider "cockroach" {
  apikey = var.cockroach_api_key
}

provider "upstash" {
  email   = var.upstash_email
  api_key = var.upstash_api_key
}

provider "redpanda" {
  client_id     = var.redpanda_client_id
  client_secret = var.redpanda_client_secret
}
