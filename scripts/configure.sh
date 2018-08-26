#!/bin/bash

set -e

TEMP_DIR="/tmp"
port=$(ctx node properties port)
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/cloudify-hello-world.$port
if [ -d ${PYTHON_FILE_SERVER_ROOT} ]; then
	echo "Removing file server root folder ${PYTHON_FILE_SERVER_ROOT}"
	rm -rf ${PYTHON_FILE_SERVER_ROOT}
fi
ctx logger info "Creating HTTP server root directory at ${PYTHON_FILE_SERVER_ROOT}"

mkdir -p ${PYTHON_FILE_SERVER_ROOT}

cd ${PYTHON_FILE_SERVER_ROOT}

index_path="hello-webpage/index.html"
image_path="hello-webpage/cloudify-logo.png"

ctx logger info "Downloading blueprint resources..."
ctx download-resource-and-render ${index_path} ${PYTHON_FILE_SERVER_ROOT}/index.html
ctx download-resource ${image_path} ${PYTHON_FILE_SERVER_ROOT}/cloudify-logo.png
