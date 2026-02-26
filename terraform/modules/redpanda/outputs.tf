output "cluster_id" {
  value = var.existing_cluster_id != null ? var.existing_cluster_id : redpanda_serverless_cluster.this[0].id
}

output "cluster_api_url" {
  value = data.redpanda_cluster.this.cluster_api_url
}

output "kafka_username" {
  value = redpanda_user.app_user.name
}
