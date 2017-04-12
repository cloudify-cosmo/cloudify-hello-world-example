#!/bin/bash

MANAGER_BLUEPRINTS_PATH="/opt/cfy/cloudify-manager-blueprints"
MANAGER_BLUEPRINT_PATH="${MANAGER_BLUEPRINTS_PATH}/simple-manager-blueprint.yaml"
INPUTS_FILE_PATH="/tmp/bootstrap_inputs.yaml"

CLI_PACKAGE_URL=$1
PRIVATE_KEY_PATH=$2
PUBLIC_IP=$3
PRIVATE_IP=$4
MANAGER_USER=$5

echo "Installing Cloudify's CLI..."

which rpm

if [ "$?" -eq "0" ]; then
    sudo rpm -i ${CLI_PACKAGE_URL}
else
    wget ${CLI_PACKAGE_URL} -O cloudify-cli.deb
    sudo dpkg -i cloudify-cli.deb
fi

set -e

echo "Creating inputs file.."
echo "public_ip: ${PUBLIC_IP}
private_ip: ${PRIVATE_IP}
ssh_user: ${MANAGER_USER}
ssh_key_filename: ${PRIVATE_KEY_PATH}
admin_username: admin
admin_password: admin" > ${INPUTS_FILE_PATH}
cat ${INPUTS_FILE_PATH}

echo "Setting permissions for private key file: ${PRIVATE_KEY_PATH}"
chmod 400 ${PRIVATE_KEY_PATH}

echo "Bootstrapping cloudify manager.."
cfy bootstrap ${MANAGER_BLUEPRINT_PATH} -i ${INPUTS_FILE_PATH} -v --keep-up-on-failure
cfy status

echo "Bootstrap completed successfully!"
