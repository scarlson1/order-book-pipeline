data "oci_identity_availability_domains" "ads" {
  compartment_id = var.oci_tenancy_ocid
}

resource "oci_core_vcn" "main" {
  compartment_id = var.oci_compartment_ocid
  cidr_block     = "10.40.0.0/16"
  display_name   = "${var.project_name}-vcn"
  dns_label      = "obvcn"
}

resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.oci_compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  enabled        = true
  display_name   = "${var.project_name}-igw"
}

resource "oci_core_route_table" "public" {
  compartment_id = var.oci_compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.project_name}-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.igw.id
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.oci_compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.project_name}-public-sl"

  ingress_security_rules {
    protocol = "6"
    source   = var.oci_admin_cidr
    tcp_options { 
        min = 22
        max = 22 
    }
  }

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.oci_compartment_ocid
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = "10.40.1.0/24"
  display_name               = "${var.project_name}-public-subnet"
  dns_label                  = "obpub"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public.id]
  prohibit_public_ip_on_vnic = false
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.oci_compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = var.oci_vm_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "app_vm" {
  compartment_id      = var.oci_compartment_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.oci_ad_index].name
  display_name        = "${var.project_name}-vm"
  shape               = var.oci_vm_shape

  shape_config {
    ocpus         = var.oci_vm_ocpus
    memory_in_gbs = var.oci_vm_memory_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    hostname_label   = "orderbookvm"
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.oci_boot_volume_gb
  }

  metadata = {
    ssh_authorized_keys = var.oci_ssh_public_key
  }
}

# CockroachDB serverless cluster
resource "cockroach_cluster" "db" {
  name           = var.cockroach_cluster_name
  cloud_provider = var.cockroach_cloud_provider
  plan           = "BASIC"
  serverless     = {}
  regions = [{ name = var.cockroach_region }]
  delete_protection = false
}

# Upstash Redis
resource "upstash_redis_database" "cache" {
  database_name = "${var.project_name}-redis"
  region        = var.upstash_region
  tls           = "true"
  multi_zone    = "false"
}

# Redpanda Serverless
resource "redpanda_resource_group" "rg" {
  name = var.redpanda_resource_group_name
}

resource "redpanda_serverless_cluster" "kafka" {
  name              = var.redpanda_cluster_name
  resource_group_id = redpanda_resource_group.rg.id
  serverless_region = var.redpanda_serverless_region
}

data "redpanda_cluster" "kafka" {
  id = redpanda_serverless_cluster.kafka.id
}

resource "redpanda_user" "app_user" {
  name            = var.redpanda_kafka_user
  password        = var.redpanda_kafka_password
  mechanism       = "scram-sha-256"
  cluster_api_url = data.redpanda_cluster.kafka.cluster_api_url
  allow_deletion  = true
}

resource "redpanda_topic" "raw" {
  name               = "orderbook.raw"
  partition_count    = 3
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.kafka.cluster_api_url
}

resource "redpanda_topic" "metrics" {
  name               = "orderbook.metrics"
  partition_count    = 3
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.kafka.cluster_api_url
}

resource "redpanda_topic" "windowed" {
  name               = "orderbook.metrics.windowed"
  partition_count    = 3
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.kafka.cluster_api_url
}

resource "redpanda_topic" "alerts" {
  name               = "orderbook.alerts"
  partition_count    = 1
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.kafka.cluster_api_url
}
