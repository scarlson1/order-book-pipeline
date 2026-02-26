terraform {
  required_providers {
    upstash = {
      source = "upstash/upstash"
    }
  }
}

resource "upstash_redis_database" "this" {
  database_name  = var.database_name
  region         = "global"
  primary_region = var.region
  tls            = var.tls
}
