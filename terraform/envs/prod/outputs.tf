output "oci_vm_public_ip" {
  value = module.oci_vm.instance_public_ip
}

output "oci_vm_id" {
  value = module.oci_vm.instance_id
}

# output "oci_vm_public_ip" {
#   value = oci_core_public_ip.vm_public_ip.ip_address
# }

output "cockroach_cluster_id" {
  value = module.cockroach.cluster_id
}

output "cockroach_cluster_name" {
  value = module.cockroach.cluster_name
}

output "cockroach_cloud_provider" {
  value = module.cockroach.cloud_provider
}

output "cockroach_region" {
  value = module.cockroach.region
}

output "cockroach_sql_port" {
  value = module.cockroach.sql_port
}

output "cockroach_default_database" {
  value = module.cockroach.default_database
}

output "cockroach_default_sslmode" {
  value = "require"
}

# output "upstash_redis_endpoint" {
#   value = module.upstash.endpoint
# }

# output "upstash_redis_port" {
#   value = module.upstash.port
# }

# output "upstash_redis_tls" {
#   value = true
# }

output "redis_cloud_endpoint" {
  value = module.redis_cloud.endpoint
}

output "redis_cloud_host" {
  value = module.redis_cloud.host
}

output "redis_cloud_port" {
  value = module.redis_cloud.port
}

output "redis_cloud_tls" {
  value = true
}

output "redpanda_cluster_id" {
  value = var.enable_redpanda ? module.redpanda[0].cluster_id : null
}

output "redpanda_cluster_api_url" {
  value = var.enable_redpanda ? module.redpanda[0].cluster_api_url : null
}

output "redpanda_kafka_username" {
  value = var.enable_redpanda ? module.redpanda[0].kafka_username : null
}

output "redpanda_topic_prefix" {
  value = var.redpanda_topic_prefix
}

output "redpanda_security_protocol" {
  value = "SASL_SSL"
}

output "redpanda_sasl_mechanism" {
  value = "SCRAM-SHA-256"
}

output "redpanda_ssl_check_hostname" {
  value = true
}

output "redpanda_kafka_port" {
  value = 9092
}
