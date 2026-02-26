resource "cockroach_cluster" "this" {
  name              = var.cluster_name
  cloud_provider    = var.cloud_provider
  plan              = "BASIC"
  serverless        = {}
  regions           = [{ name = var.region }]
  delete_protection = var.delete_protection
}
