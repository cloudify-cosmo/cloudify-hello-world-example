#!/bin/bash

set -e

TEMP_DIR="/tmp"
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/python-simple-http-webserver
if [ -d ${PYTHON_FILE_SERVER_ROOT} ]; then
	echo "Removing file server root folder ${PYTHON_FILE_SERVER_ROOT}"
	rm -rf ${PYTHON_FILE_SERVER_ROOT}
fi
ctx logger info "Creating HTTP server root directory at ${PYTHON_FILE_SERVER_ROOT}"

mkdir -p ${PYTHON_FILE_SERVER_ROOT}

cd ${PYTHON_FILE_SERVER_ROOT}

index_path="index.html"
image_path="images/cloudify-logo.png"

ctx logger info "Downloading blueprint resources..."
ctx download-resource ${index_path} ${PYTHON_FILE_SERVER_ROOT}/index.html
ctx download-resource ${image_path} ${PYTHON_FILE_SERVER_ROOT}/cloudify-logo.png

ctx logger info "Preparing index.html..."
sed -i "s|{0}|$(ctx blueprint id)|g" ${PYTHON_FILE_SERVER_ROOT}/index.html
sed -i "s|{1}|$(ctx deployment id)|g" ${PYTHON_FILE_SERVER_ROOT}/index.html
sed -i "s|{2}|$(ctx node id)|g" ${PYTHON_FILE_SERVER_ROOT}/index.html
sed -i "s|{3}|cloudify-logo.png|g" ${PYTHON_FILE_SERVER_ROOT}/index.html
