FROM ubuntu:14.04

RUN apt-get update && \
    apt-get -f install -y && \
    apt-get install -y python python-dev python-pip curl wget git libssl-dev && \
    pip install pip --upgrade && \
    hash -d pip && \
    pip install virtualenv

ENV HOME /root
