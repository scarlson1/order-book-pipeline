terraform {
  required_providers {
    rediscloud = {
      source = "RedisLabs/rediscloud"
    }
  }
}

# If using the free/Essentials tier, use this resource instead:
resource "rediscloud_essentials_database" "this" {
  subscription_id = var.subscription_id
  name            = var.database_name
  password        = var.password
  data_persistence     = "none"
  replication          = false
}

# resource "rediscloud_subscription_database" "this" {
#   subscription_id      = var.subscription_id # rediscloud_subscription.this.id
#   name                 = var.database_name
#   protocol             = "redis"
#   memory_limit_in_gb   = var.memory_limit_mb / 1024
#   data_persistence     = "none"
#   password             = var.password
#   replication          = false

#   throughput_measurement_by    = "operations-per-second"
#   throughput_measurement_value = 1000
# }

# # Look up available cloud regions
# data "rediscloud_payment_method" "card" {
#   card_type    = "Visa"  # adjust to your payment method, or remove for free tier
# }

# resource "rediscloud_subscription" "this" {
#   name              = var.subscription_name
#   payment_method_id = data.rediscloud_payment_method.card.id  # remove if free tier

#   cloud_provider {
#     provider = var.cloud_provider
#     region {
#       region                       = var.region
#       multiple_availability_zones  = false
#       networking_deployment_cidr   = "10.10.0.0/24"
#     }
#   }

#   database {
#     name                         = var.database_name
#     protocol                     = "redis"
#     memory_limit_in_gb           = var.memory_limit_mb / 1024
#     data_persistence             = "none"
#     throughput_measurement_by    = "operations-per-second"
#     throughput_measurement_value = 1000
#     password                     = var.password

#     alert {
#       name  = "dataset-size"
#       value = 80
#     }
#   }
# }