#!/bin/bash -e

set -e

TEMP_DIR="/tmp"
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/python-simple-http-webserver
PID_FILE="server.pid"

PID=`cat ${PYTHON_FILE_SERVER_ROOT}/${PID_FILE}`
echo "Shutting down file server. pid = ${PID}"
kill -9 ${PID} || exit $?
echo "Deleting file server root directory (${PYTHON_FILE_SERVER_ROOT})"
rm -rf ${PYTHON_FILE_SERVER_ROOT}