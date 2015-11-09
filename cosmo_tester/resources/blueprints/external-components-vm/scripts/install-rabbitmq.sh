#!/bin/bash -e

deploy_blueprint_resource ()
{
    ###
    # Deploys a blueprint resource to a given path.
    ###
    source_path=$1
    destination_path=$2

    ctx logger info "Deploying ${source_path} to ${destination_path}..."
    tmp_file=$(ctx download-resource-and-render ${source_path})
    sudo mv ${tmp_file} ${destination_path}
}

service_identifier=cloudify-rabbitmq

ERLANG_SOURCE_URL=https://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/erlang-17.4-1.el6.x86_64.rpm
RABBITMQ_SOURCE_URL=https://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/rabbitmq-server-3.5.3-1.noarch.rpm
RABBITMQ_USERNAME=cloudify
RABBITMQ_PASSWORD=c10udify

curl -O ${ERLANG_SOURCE_URL}
curl -O ${RABBITMQ_SOURCE_URL}

sudo yum install -y erlang-17.4-1.el6.x86_64.rpm
sudo yum install -y rabbitmq-server-3.5.3-1.noarch.rpm

# Disabling selinux as this system is purely for temporary testing (and it's breaking rabbit)
sudo setenforce 0

ctx logger info "Deploying systemd .service file..."
deploy_blueprint_resource "config/${service_identifier}.service" "/usr/lib/systemd/system/${service_identifier}.service"

ctx logger info "Enabling systemd .service..."
sudo systemctl enable ${service_identifier}.service &>/dev/null
sudo systemctl daemon-reload >/dev/null

sudo systemctl start ${service_identifier}.service

# Allow time for rabbit to finish starting since systemctl returns before it has done so
# TODO: This would be better with an actual check
sleep 30

ctx logger info "Disabling RabbitMQ guest user"
sudo rabbitmqctl clear_permissions guest
ctx logger info "Deleting RabbitMQ guest user"
sudo rabbitmqctl delete_user guest

ctx logger info "Creating new RabbitMQ user and setting permissions"
sudo rabbitmqctl add_user ${RABBITMQ_USERNAME} ${RABBITMQ_PASSWORD}
sudo rabbitmqctl set_permissions ${RABBITMQ_USERNAME} '.*' '.*' '.*'

sudo systemctl stop ${service_identifier}.service
