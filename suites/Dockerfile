FROM ubuntu:14.04

ENV HOME /root
ENV LANG C.UTF-8

RUN apt-get update && \
    apt-get -f install -y && \
    apt-get install -y \
        curl \
        wget \
        git \
        python \
        python-dev \
        python-pip \
        libxml2-dev \
        libxslt-dev \
        lib32z1-dev && \
    pip install pip --upgrade

# run pip in a separate RUN command after pip upgrade
RUN pip install virtualenv wheel
ADD wheel-requirements.txt /wheel-requirements.txt
RUN pip wheel --wheel-dir=/wheels -r /wheel-requirements.txt
