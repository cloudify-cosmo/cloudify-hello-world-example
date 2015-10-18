#!/bin/bash -e

curl -O https://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/jre1.8.0_45-1.8.0_45-fcs.x86_64.rpm
sudo yum install -y jre1.8.0_45-1.8.0_45-fcs.x86_64.rpm

curl -O https://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/elasticsearch-1.6.0.noarch.rpm
sudo yum install -y elasticsearch-1.6.0.noarch.rpm

sudo systemctl enable elasticsearch.service &>/dev/null