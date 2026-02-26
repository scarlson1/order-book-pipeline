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
