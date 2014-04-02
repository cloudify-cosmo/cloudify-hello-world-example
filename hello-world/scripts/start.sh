#!/bin/bash -e

set -e

. ${CLOUDIFY_LOGGING}

TEMP_DIR="/tmp"
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/python-simple-http-webserver
PID_FILE="server.pid"

info "Starting HTTP server from ${PYTHON_FILE_SERVER_ROOT}"

echo "Changing directory to ${PYTHON_FILE_SERVER_ROOT}"
cd ${PYTHON_FILE_SERVER_ROOT}
info "Starting SimpleHTTPServer"
nohup python -m SimpleHTTPServer ${port} > /dev/null 2>&1 &
echo $! > ${PID_FILE}

info "Waiting for server to launch"

STARTED=false
for i in $(seq 1 15)
do
	if wget http://localhost:${port} 2>/dev/null ; then
		info "Server is up."
		STARTED=true
    	break
	else
		info "Server not up. waiting 1 second."
		sleep 1
	fi	
done
if [ ${STARTED} = false ]; then
	error "Failed starting web server in 15 seconds."
	exit 1
fi
