#!/bin/bash

MANAGER_BLUEPRINTS_PATH="/usr/local/opt/cfy/cloudify-manager-blueprints"
MANAGER_BLUEPRINT_PATH="${MANAGER_BLUEPRINTS_PATH}/simple-manager-blueprint.yaml"
INPUTS_FILE_PATH="/tmp/bootstrap_inputs.yaml"

CLI_PACKAGE_URL=$1
PRIVATE_KEY_PATH=$2
PUBLIC_IP=$3
PRIVATE_IP=$4
MANAGER_USER=$5

echo "Using CLI package: ${CLI_PACKAGE_URL}"


curl ${CLI_PACKAGE_URL} -o /tmp/package.pkg
echo $MACINCLOUD_PASSWORD | sudo -S installer -pkg /tmp/package.pkg -target /

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
/usr/local/opt/cfy/bin/cfy bootstrap ${MANAGER_BLUEPRINT_PATH} -i ${INPUTS_FILE_PATH} -v --keep-up-on-failure
/usr/local/opt/cfy/bin/cfy status

echo "Bootstrap completed successfully!"
