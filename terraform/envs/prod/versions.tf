terraform {
  required_version = ">= 1.12.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 8.2"
    }
    cockroach = {
      source  = "cockroachdb/cockroach"
      version = "~> 1.17"
    }
    # upstash = {
    #   source  = "upstash/upstash"
    #   version = ">= 1.0.0, < 2.0.0"
    # }
    rediscloud = {
      source  = "RedisLabs/rediscloud"
      version = "~> 1.7"
    }
    redpanda = {
      source  = "redpanda-data/redpanda"
      version = "~> 1.6"
    }
  }
}
