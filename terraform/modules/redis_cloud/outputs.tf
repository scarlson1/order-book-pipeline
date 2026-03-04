output "endpoint" {
  value = rediscloud_subscription_database.this.public_endpoint
}

output "port" {
  value = split(":", rediscloud_subscription_database.this.public_endpoint)[1]
}

output "host" {
  value = split(":", rediscloud_subscription_database.this.public_endpoint)[0]
}