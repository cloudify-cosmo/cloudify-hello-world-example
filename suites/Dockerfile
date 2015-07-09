FROM ubuntu:14.04

RUN apt-get update
RUN apt-get -f install -y
RUN apt-get install -y python libxml2-dev libxslt-dev python-dev lib32z1-dev python-pip curl wget git
RUN pip install pip --upgrade
RUN pip install virtualenv

ENV HOME /root
ENV LANG C.UTF-8
