#!/bin/sh

TAG=${1:-latest}

docker build -t yatheo/swarm_consul_registrator:$TAG . && docker push yatheo/swarm_consul_registrator:$TAG
