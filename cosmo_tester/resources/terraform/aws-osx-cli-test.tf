
variable "manager_user" {}
variable "manager_image" {}
variable "manager_flavor" {}
variable "osx_public_ip" {}
variable "osx_user" {}
variable "osx_password" {}
variable "osx_ssh_key" {}
variable "cli_package_url" {}

# MANAGER
output "manager_public_ip_address" { value = "${aws_instance.manager.public_ip}" }

provider "aws" {}

resource "aws_vpc" "osx-cli-test" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_internet_gateway" "osx-cli-test" {
  vpc_id = "${aws_vpc.osx-cli-test.id}"
}

resource "aws_route" "internet_access" {
  route_table_id         = "${aws_vpc.osx-cli-test.main_route_table_id}"
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = "${aws_internet_gateway.osx-cli-test.id}"
}

resource "aws_subnet" "osx-cli-test" {
  vpc_id                  = "${aws_vpc.osx-cli-test.id}"
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
}

resource "aws_key_pair" "osx-cli-test" {
  key_name_prefix   = "osx-cli-test"
  public_key = "${var.osx_ssh_key}"
}

resource "aws_security_group" "osx-cli-test" {
  name = "osx-cli-test"
  description = "Used by OSX-CLI test"
  vpc_id      = "${aws_vpc.osx-cli-test.id}"

  ingress {
    from_port = 0
    to_port = 65535
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# MANAGER
resource "aws_instance" "manager" {
  ami           = "${var.manager_image}"
  instance_type = "${var.manager_flavor}"
  subnet_id = "${aws_subnet.osx-cli-test.id}"
  key_name = "${aws_key_pair.osx-cli-test.id}"
  vpc_security_group_ids = ["${aws_security_group.osx-cli-test.id}"]
  tags {
    "Name" = "system-test OSX cli-test"
  }
}

# macincoud Dedicated server
resource "null_resource" "macincloud" {
  connection {
    agent = false
    timeout = "30m"
    host = "${var.osx_public_ip}"
    user = "${var.osx_user}"
    password = "${var.osx_password}"
  }

  triggers {
    instance_ids = "${element(aws_instance.manager.*.id, count.index)}"
  }

  provisioner "file" {
    source = "scripts/osx-cli-test.sh"
    destination = "/tmp/osx-cli-test.sh"

  }

  provisioner "file" {
    source = "/var/lib/jenkins/.ssh/macincloud/macincloud.pem"
    destination = "/tmp/key.pem"

  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x /tmp/osx-cli-test.sh",
      "export MACINCLOUD_PASSWORD=${var.osx_password}",
      "ssh -i /tmp/key.pem -o 'StrictHostKeychecking=no' centos@${aws_instance.manager.public_ip} 'sudo yum update openssl -y'",
      "/tmp/osx-cli-test.sh ${var.cli_package_url} /tmp/key.pem ${aws_instance.manager.public_ip} ${aws_instance.manager.private_ip} ${var.manager_user}",
      "rm -rf /tmp/key.pem"
    ]
  }
}
