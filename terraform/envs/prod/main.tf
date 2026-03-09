module "oci_vm" {
  source = "../../modules/oci_vm"

  project_name     = var.project_name
  tenancy_ocid     = var.oci_tenancy_ocid
  compartment_ocid = var.oci_compartment_ocid
  ad_index         = var.oci_ad_index
  admin_cidr       = var.oci_admin_cidr
  vm_shape         = var.oci_vm_shape
  vm_ocpus         = var.oci_vm_ocpus
  vm_memory_gb     = var.oci_vm_memory_gb
  boot_volume_gb   = var.oci_boot_volume_gb
  ssh_public_key   = var.oci_ssh_public_key
}

module "cockroach" {
  source = "../../modules/cockroach"

  cluster_name      = var.cockroach_cluster_name
  cloud_provider    = var.cockroach_cloud_provider
  region            = var.cockroach_region
  delete_protection = var.cockroach_delete_protection
}

# module "upstash" {
#   source = "../../modules/upstash"

#   database_name = "${var.project_name}-redis"
#   region        = var.upstash_region
#   tls           = true
# }

module "redis_cloud" {
  source = "../../modules/redis_cloud"

  # subscription_name = "${var.project_name}-sub"
  database_name     = "orderbook-pipeline" # "${var.project_name}-redis"
  region            = var.redis_cloud_region
  cloud_provider    = var.redis_cloud_provider
  memory_limit_mb   = var.redis_cloud_memory_mb
  password          = var.redis_cloud_password
  tls               = true
  subscription_id   = var.redis_cloud_subscription_id
  subscription_name = "orderbook-pipeline" # "${var.project_name}-sub"
}

module "redpanda" {
  count  = var.enable_redpanda ? 1 : 0
  source = "../../modules/redpanda"

  resource_group_name        = var.redpanda_resource_group_name
  existing_resource_group_id = var.redpanda_existing_resource_group_id
  cluster_name               = var.redpanda_cluster_name
  existing_cluster_id        = var.redpanda_existing_cluster_id
  serverless_region          = var.redpanda_serverless_region
  kafka_user                 = var.redpanda_kafka_user
  kafka_password             = var.redpanda_kafka_password
  topic_prefix               = var.redpanda_topic_prefix
}
