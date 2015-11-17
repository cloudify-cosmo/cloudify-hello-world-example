#!/bin/bash -e

sudo pkill -f 'bin/rabbitmq'

ctx logger info "Starting RabbitMQ Service..."
sudo systemctl start cloudify-rabbitmq.service
