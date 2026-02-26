output "instance_id" {
  value = oci_core_instance.app_vm.id
}

output "instance_public_ip" {
  value = data.oci_core_vnic.app_vm.public_ip_address
}

output "vcn_id" {
  value = oci_core_vcn.main.id
}

output "subnet_id" {
  value = oci_core_subnet.public.id
}
