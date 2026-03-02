output "oci_vm_public_ip" {
  value = module.oci_vm.instance_public_ip
}

output "oci_vm_id" {
  value = module.oci_vm.instance_id
}

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

output "upstash_redis_endpoint" {
  value = module.upstash.endpoint
}

output "upstash_redis_port" {
  value = module.upstash.port
}

output "upstash_redis_tls" {
  value = true
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
