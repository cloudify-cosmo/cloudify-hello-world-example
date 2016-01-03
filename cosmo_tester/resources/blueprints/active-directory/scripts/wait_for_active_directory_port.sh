#!/bin/bash
HOST_IP=$public_ip
PORT=$port
TIMEOUT_SEC="$(($timeout_minutes * 60))"
function wait_for_port
{
    /bin/netcat -z -w$3 $1 $2
    if [ $? -ne 0 ] && $fail_on_timeout; then
        echo "active directory endpoint $1:$2 not avilable after $3 seconds."
        exit 1
    fi
}

wait_for_port $HOST_IP $PORT $TIMEOUT_SEC