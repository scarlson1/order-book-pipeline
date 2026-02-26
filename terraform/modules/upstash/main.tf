resource "upstash_redis_database" "this" {
  database_name = var.database_name
  region        = var.region
  tls           = var.tls
  multi_zone    = var.multi_zone
}
