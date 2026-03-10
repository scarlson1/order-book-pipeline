output "instance_id" {
  value = oci_core_instance.app_vm.id
}

output "instance_public_ip" {
  value = oci_core_public_ip.vm_public_ip.ip_address
}

output "vcn_id" {
  value = oci_core_vcn.main.id
}

output "subnet_id" {
  value = oci_core_subnet.public.id
}