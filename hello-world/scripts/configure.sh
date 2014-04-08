#!/bin/bash

set -e

. ${CLOUDIFY_LOGGING}
. ${CLOUDIFY_FILE_SERVER}

TEMP_DIR="/tmp"
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/python-simple-http-webserver
if [ -d ${PYTHON_FILE_SERVER_ROOT} ]; then
	echo "Removing file server root folder ${PYTHON_FILE_SERVER_ROOT}"
	rm -rf ${PYTHON_FILE_SERVER_ROOT}
fi
cfy_info "Creating HTTP server root directory at ${PYTHON_FILE_SERVER_ROOT}"
mkdir -p ${PYTHON_FILE_SERVER_ROOT}

echo "Changing directory to ${PYTHON_FILE_SERVER_ROOT}"
cd ${PYTHON_FILE_SERVER_ROOT}
cfy_info "Downloading index to web server"
cfy_download_resource ${index_path} -O ${PYTHON_FILE_SERVER_ROOT}/index.html
cfy_info "Downloading image to web server" -O ${PYTHON_FILE_SERVER_ROOT}/cloudify-logo.png
cfy_download_resource ${image_path}

# Add dynamic data

echo "Generating dynamic data"

sed -i "s|{0}|${CLOUDIFY_BLUEPRINT_ID}|g" ${PYTHON_FILE_SERVER_ROOT}/index.html
sed -i "s|{1}|${CLOUDIFY_DEPLOYMENT_ID}|g" ${PYTHON_FILE_SERVER_ROOT}/index.html
sed -i "s|{2}|${CLOUDIFY_NODE_ID}|g" ${PYTHON_FILE_SERVER_ROOT}/index.html
sed -i "s|{3}|cloudify-logo.png|g" ${PYTHON_FILE_SERVER_ROOT}/index.html

echo "index file is ready"

