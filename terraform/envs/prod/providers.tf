provider "oci" {
  tenancy_ocid     = var.oci_tenancy_ocid
  user_ocid        = var.oci_user_ocid
  fingerprint      = var.oci_fingerprint
  private_key_path = var.oci_private_key_path
  region           = var.oci_region
}

provider "cockroach" {
  apikey = var.cockroach_api_key
}

provider "upstash" {
  email   = var.upstash_email
  api_key = var.upstash_api_key
}

provider "redpanda" {
  client_id     = var.redpanda_client_id
  client_secret = var.redpanda_client_secret
}
