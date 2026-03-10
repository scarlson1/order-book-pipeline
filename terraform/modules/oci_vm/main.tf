terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_ocid
  cidr_block     = "10.40.0.0/16"
  display_name   = "${var.project_name}-vcn"
  dns_label      = "obvcn"
}

resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  enabled        = true
  display_name   = "${var.project_name}-igw"
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.project_name}-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.igw.id
  }
}

# Streamlit Community Cloud egress IPs - may change without notice.
# Source: https://docs.streamlit.io/deploy/streamlit-community-cloud/status
locals {
  streamlit_egress_cidrs = toset([
    "35.230.127.150/32",
    "35.203.151.101/32",
    "34.19.100.134/32",
    "34.83.176.217/32",
    "35.230.58.211/32",
    "35.203.187.165/32",
    "35.185.209.55/32",
    "34.127.88.74/32",
    "34.127.0.121/32",
    "35.230.78.192/32",
    "35.247.110.67/32",
    "35.197.92.111/32",
    "34.168.247.159/32",
    "35.230.56.30/32",
    "34.127.33.101/32",
    "35.227.190.87/32",
    "35.199.156.97/32",
    "34.82.135.155/32",
  ])
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${var.project_name}-public-sl"

  # SSH from admin IP (for local development)
  ingress_security_rules {
    protocol = "6"
    source   = var.admin_cidr
    tcp_options {
      min = 22
      max = 22
    }
  }

  # SSH from anywhere (for GitHub Actions deployments)
  # SSH key authentication is used, so this is secure
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 22
      max = 22
    }
  }

  # redpanda console
  ingress_security_rules {
    protocol = "6"
    source   = var.admin_cidr   # your IP only
    tcp_options {
      min = 8080
      max = 8080
    }
  }

  # Flink REST API (port 8081) - for Streamlit Cloud health checks
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 8081
      max = 8081
    }
  }

  # Redpanda Admin API (9644) - open to all (Streamlit no longer publishes egress IPs)
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 9644
      max = 9644
    }
  }

  # Redpanda API (9093) - open to all (Streamlit no longer publishes egress IPs)
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options {
      min = 9093
      max = 9093
    }
  }

  # Redpanda Kafka API (9092) - Streamlit Community Cloud egress IPs only
  dynamic "ingress_security_rules" {
    for_each = local.streamlit_egress_cidrs
    content {
      protocol = "6"
      source   = ingress_security_rules.value
      tcp_options {
        min = 9093
        max = 9093
      }
    }
  }

  # Redpanda Admin API (9644) - Streamlit Community Cloud egress IPs only
  dynamic "ingress_security_rules" {
    for_each = local.streamlit_egress_cidrs
    content {
      protocol = "6"
      source   = ingress_security_rules.value
      tcp_options {
        min = 9644
        max = 9644
      }
    }
  }

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = "10.40.1.0/24"
  display_name               = "${var.project_name}-public-subnet"
  dns_label                  = "obpub"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public.id]
  prohibit_public_ip_on_vnic = false
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = var.vm_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "app_vm" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.ad_index].name
  display_name        = "${var.project_name}-vm"
  shape               = var.vm_shape

  shape_config {
    ocpus         = var.vm_ocpus
    memory_in_gbs = var.vm_memory_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = false
    hostname_label   = "orderbookvm"
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [source_details]
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(file("${path.module}/cloud-init.yaml"))
  }
}

data "oci_core_vnic_attachments" "app_vm" {
  compartment_id = var.compartment_ocid
  instance_id    = oci_core_instance.app_vm.id
}

data "oci_core_vnic" "app_vm" {
  vnic_id = data.oci_core_vnic_attachments.app_vm.vnic_attachments[0].vnic_id
}

data "oci_core_private_ips" "app_vm" {
  vnic_id = data.oci_core_vnic.app_vm.id
}

# Reserved public IP - attached to VM's primary VNIC, survives VM recreation
resource "oci_core_public_ip" "vm_public_ip" {
  compartment_id = var.compartment_ocid
  lifetime       = "RESERVED"
  display_name   = "${var.project_name}-public-ip"
  private_ip_id  = data.oci_core_private_ips.app_vm.private_ips[0].id

  lifecycle {
    prevent_destroy = true
  }
}
