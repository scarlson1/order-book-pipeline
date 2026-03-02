output "cluster_id" {
  value = cockroach_cluster.this.id
}

output "cluster_name" {
  value = cockroach_cluster.this.name
}

output "cloud_provider" {
  value = cockroach_cluster.this.cloud_provider
}

output "region" {
  value = var.region
}

output "sql_port" {
  value = 26257
}

output "default_database" {
  value = "pipeline"
}
