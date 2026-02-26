output "cluster_id" {
  value = redpanda_serverless_cluster.this.id
}

output "cluster_api_url" {
  value = data.redpanda_cluster.this.cluster_api_url
}

output "kafka_username" {
  value = redpanda_user.app_user.name
}
