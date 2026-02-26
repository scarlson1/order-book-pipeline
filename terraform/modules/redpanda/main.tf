terraform {
  required_providers {
    redpanda = {
      source = "redpanda-data/redpanda"
    }
  }
}

resource "redpanda_resource_group" "this" {
  count = var.existing_resource_group_id == null && var.existing_cluster_id == null ? 1 : 0
  name  = var.resource_group_name
}

resource "redpanda_serverless_cluster" "this" {
  count             = var.existing_cluster_id == null ? 1 : 0
  name              = var.cluster_name
  resource_group_id = var.existing_resource_group_id != null ? var.existing_resource_group_id : redpanda_resource_group.this[0].id
  serverless_region = var.serverless_region
}

data "redpanda_cluster" "this" {
  id = var.existing_cluster_id != null ? var.existing_cluster_id : redpanda_serverless_cluster.this[0].id
}

resource "redpanda_user" "app_user" {
  name            = var.kafka_user
  password_wo     = var.kafka_password
  mechanism       = var.kafka_mechanism
  cluster_api_url = data.redpanda_cluster.this.cluster_api_url
  allow_deletion  = true
}

resource "redpanda_topic" "raw" {
  name               = "${var.topic_prefix}.raw"
  partition_count    = 3
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.this.cluster_api_url
}

resource "redpanda_topic" "metrics" {
  name               = "${var.topic_prefix}.metrics"
  partition_count    = 3
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.this.cluster_api_url
}

resource "redpanda_topic" "windowed" {
  name               = "${var.topic_prefix}.metrics.windowed"
  partition_count    = 3
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.this.cluster_api_url
}

resource "redpanda_topic" "alerts" {
  name               = "${var.topic_prefix}.alerts"
  partition_count    = 1
  replication_factor = 3
  cluster_api_url    = data.redpanda_cluster.this.cluster_api_url
}
