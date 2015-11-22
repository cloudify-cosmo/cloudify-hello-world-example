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

deploy_ssl_certificate () {
  private_or_public=${1}
  destination=${2}
  group=${3}
  cert=${4}

  # Root owner, with permissions set below, allow anyone to read a public cert, and allow the owner to read a private cert, but not change it, mitigating risk in the event of the associated service being vulnerable.
  ownership=root.${group}

  if [[ ${private_or_public} == "private" ]]; then
    # This check should probably be done using an openssl command
    if [[ "${cert}" =~ "PRIVATE KEY" ]]; then
      # Owner read, Group read, Others no access
      permissions=440
    else
      sys_error "Private certificate is expected to begin with a line containing 'PRIVATE KEY'."
    fi
  elif [[ ${private_or_public} == "public" ]]; then
    # This check should probably be done using an openssl command
    if [[ "${cert}" =~ "BEGIN CERTIFICATE" ]]; then
      # Owner read, Group read, Others read
      permissions=444
    else
      # This should probably be done using an openssl command
      sys_error "Public certificate is expected to begin with a line containing 'BEGIN CERTIFICATE'."
    fi
  else
    sys_error "Certificates may only be 'private' or 'public', not '${private_or_public}'"
  fi

  ctx logger info "Deploying ${private_or_public} SSL certificate in ${destination} for group ${group}"
  echo "${cert}" | sudo tee ${destination} >/dev/null

  ctx logger info "Setting permissions (${permissions}) and ownership (${ownership}) of SSL certificate at ${ddestination}"
  # Set permissions first as the tee with sudo should mean its owner and group are root, leaving a negligible window for it to be accessed by an unauthorised user
  sudo chmod ${permissions} ${destination}
  sudo chown ${ownership} ${destination}
}

service_identifier=cloudify-rabbitmq

ERLANG_SOURCE_URL=https://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/erlang-17.4-1.el6.x86_64.rpm
RABBITMQ_SOURCE_URL=https://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/rabbitmq-server-3.5.3-1.noarch.rpm
RABBITMQ_USERNAME=cloudify
RABBITMQ_PASSWORD=c10udify

RABBITMQ_CERT_PUBLIC="$(ctx node properties broker_ssl_public_cert)"
RABBITMQ_CERT_PRIVATE="$(ctx node properties broker_ssl_private_cert)"

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

if [[ -n "${RABBITMQ_CERT_PRIVATE}" ]]; then
  if [[ -n "${RABBITMQ_CERT_PUBLIC}" ]]; then
    deploy_ssl_certificate private "/etc/rabbitmq/rabbit-priv.pem" "rabbitmq" "${RABBITMQ_CERT_PRIVATE}"
    deploy_ssl_certificate public "/etc/rabbitmq/rabbit-pub.pem" "rabbitmq" "${RABBITMQ_CERT_PUBLIC}"
    # Configure for SSL
    deploy_blueprint_resource "config/rabbitmq.config-ssl" "/etc/rabbitmq/rabbitmq.config"
  else
    sys_error "When providing a private certificate for rabbitmq, the public certificate must also be supplied."
  fi
else
  if [[ -n "${RABBITMQ_CERT_PUBLIC}" ]]; then
    sys_error "When providing a public certificate for rabbitmq, the private certificate must also be supplied."
  fi
fi

sudo systemctl stop ${service_identifier}.service
