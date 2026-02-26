output "oci_vm_public_ip" {
  value = module.oci_vm.instance_public_ip
}

output "oci_vm_id" {
  value = module.oci_vm.instance_id
}

output "cockroach_cluster_id" {
  value = module.cockroach.cluster_id
}

output "upstash_redis_endpoint" {
  value = module.upstash.endpoint
}

output "upstash_redis_port" {
  value = module.upstash.port
}

output "redpanda_cluster_id" {
  value = module.redpanda.cluster_id
}

output "redpanda_cluster_api_url" {
  value = module.redpanda.cluster_api_url
}

output "redpanda_kafka_username" {
  value = module.redpanda.kafka_username
}
