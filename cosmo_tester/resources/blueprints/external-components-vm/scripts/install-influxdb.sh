#!/bin/bash -e

service_identifier="cloudify-influxdb"
curl -O https://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/influxdb-0.8.8-1.x86_64.rpm
sudo yum install -y influxdb-0.8.8-1.x86_64.rpm

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

ctx logger info "Deploying systemd .service file..."
deploy_blueprint_resource "config/${service_identifier}.service" "/usr/lib/systemd/system/${service_identifier}.service"

ctx logger info "Enabling systemd .service..."
sudo systemctl enable ${service_identifier}.service &>/dev/null
sudo systemctl daemon-reload >/dev/null

