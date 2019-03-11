
variable "resource_suffix" {}
variable "public_key_path" {}
variable "private_key_path" {}
variable "remote_key_path" {}
variable "cli_image" {}
variable "cli_flavor" {}
variable "manager_image" {}
variable "manager_flavor" {}
variable "manager_user" {}

output "router_name" { value = "${openstack_networking_router_v2.router.name}" }
output "router_id" { value = "${openstack_networking_router_v2.router.id}" }
output "network_name" { value = "${openstack_networking_network_v2.network.name}" }
output "network_id" { value = "${openstack_networking_network_v2.network.id}" }
output "subnet_name" { value = "${openstack_networking_subnet_v2.subnet.name}" }
output "subnet_id" { value = "${openstack_networking_subnet_v2.subnet.id}" }
output "security_group_name" { value = "${openstack_compute_secgroup_v2.security_group.name}" }
output "security_group_id" { value = "${openstack_compute_secgroup_v2.security_group.id}" }
output "keypair_name" { value = "${openstack_compute_keypair_v2.keypair.name}" }

# CLI
output "cli_public_ip_address" { value = "${openstack_networking_floatingip_v2.cli_floatingip.address}" }
output "cli_private_ip_address" { value = "${openstack_compute_instance_v2.cli_server.network.0.fixed_ip_v4}" }
output "cli_server_name" { value = "${openstack_compute_instance_v2.cli_server.name}" }
output "cli_server_id" { value = "${openstack_compute_instance_v2.cli_server.id}" }

# MANAGER
output "manager_public_ip_address" { value = "${openstack_networking_floatingip_v2.manager_floatingip.address}" }
output "manager_private_ip_address" { value = "${openstack_compute_instance_v2.manager_server.network.0.fixed_ip_v4}" }
output "manager_server_name" { value = "${openstack_compute_instance_v2.manager_server.name}" }
output "manager_server_id" { value = "${openstack_compute_instance_v2.manager_server.id}" }


resource "openstack_networking_router_v2" "router" {
  name = "router-${var.resource_suffix}"
  external_gateway = "dda079ce-12cf-4309-879a-8e67aec94de4"
}

resource "openstack_networking_network_v2" "network" {
  name = "network-${var.resource_suffix}"
}

resource "openstack_networking_subnet_v2" "subnet" {
  name = "subnet-${var.resource_suffix}"
  network_id = "${openstack_networking_network_v2.network.id}"
  cidr = "10.0.0.0/24"
  dns_nameservers = ["8.8.8.8", "8.8.4.4"]
}

resource "openstack_networking_router_interface_v2" "router_interface" {
  router_id = "${openstack_networking_router_v2.router.id}"
  subnet_id = "${openstack_networking_subnet_v2.subnet.id}"
}

resource "openstack_compute_secgroup_v2" "security_group" {
  name = "security_group-${var.resource_suffix}"
  description = "cloudify manager security group"
  rule {
    from_port = 22
    to_port = 22
    ip_protocol = "tcp"
    cidr = "0.0.0.0/0"
  }
  rule {
    from_port = 5985
    to_port = 5985
    ip_protocol = "tcp"
    cidr = "0.0.0.0/0"
  }
  rule {
    from_port = 80
    to_port = 80
    ip_protocol = "tcp"
    cidr = "0.0.0.0/0"
  }
  rule {
    from_port = 443
    to_port = 443
    ip_protocol = "tcp"
    cidr = "0.0.0.0/0"
  }
  # This is here for the hello world web server installed in the test
  rule {
    from_port = 8080
    to_port = 8080
    ip_protocol = "tcp"
    cidr = "0.0.0.0/0"
  }

}

resource "openstack_compute_keypair_v2" "keypair" {
  name = "keypair-${var.resource_suffix}"
  public_key = "${file("${var.public_key_path}")}"
}

# CLI
resource "openstack_networking_floatingip_v2" "cli_floatingip" {
  pool = "GATEWAY_NET"
}

resource "openstack_compute_instance_v2" "cli_server" {
  name = "cli-${var.resource_suffix}"
  image_name = "${var.cli_image}"
  flavor_name = "${var.cli_flavor}"
  key_pair = "${openstack_compute_keypair_v2.keypair.name}"
  security_groups = ["${openstack_compute_secgroup_v2.security_group.name}"]
  user_data = "${file("scripts/windows-userdata.ps1")}"

  network {
    uuid = "${openstack_networking_network_v2.network.id}"
  }

  floating_ip = "${openstack_networking_floatingip_v2.cli_floatingip.address}"

}

# MANAGER
resource "openstack_networking_floatingip_v2" "manager_floatingip" {
  pool = "GATEWAY_NET"
}

resource "openstack_compute_instance_v2" "manager_server" {
  name = "manager-${var.resource_suffix}"
  image_name = "${var.manager_image}"
  flavor_name = "${var.manager_flavor}"
  key_pair = "${openstack_compute_keypair_v2.keypair.name}"
  security_groups = ["${openstack_compute_secgroup_v2.security_group.name}"]

  network {
    uuid = "${openstack_networking_network_v2.network.id}"
  }

  floating_ip = "${openstack_networking_floatingip_v2.manager_floatingip.address}"

  connection {
    type = "ssh"
    user = "${var.manager_user}"
    private_key = "${file("${var.private_key_path}")}"
    timeout = "10m"
    agent = "false"
  }

    provisioner "file" {
    source = "${var.private_key_path}"
    destination = "/tmp/key.pem"
  }

  provisioner "remote-exec" {
    inline = [
      "echo Setting permissions for private key file: ${var.remote_key_path}",
      "sudo cp /tmp/key.pem ${var.remote_key_path}",
      "sudo chown cfyuser: ${var.remote_key_path}",
      "sudo chmod 400 ${var.remote_key_path}",
      "sudo touch /opt/manager/sanity_mode",
      "sudo chown cfyuser:cfyuser /opt/manager/sanity_mode",
      "sudo chmod 440 /opt/manager/sanity_mode"
    ]
  }

}
