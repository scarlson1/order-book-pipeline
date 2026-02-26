output "oci_vm_public_ip" {
  value = oci_core_instance.app_vm.public_ip
}

output "cockroach_cluster_id" {
  value = cockroach_cluster.db.id
}

output "upstash_redis_endpoint" {
  value = upstash_redis_database.cache.endpoint
}

output "upstash_redis_port" {
  value = upstash_redis_database.cache.port
}

output "redpanda_cluster_id" {
  value = redpanda_serverless_cluster.kafka.id
}

output "redpanda_cluster_api_url" {
  value = data.redpanda_cluster.kafka.cluster_api_url
}

output "redpanda_kafka_username" {
  value = redpanda_user.app_user.name
}
