# docker-swarm-register

Run swarm-registrator as docker container:

`docker run -d  --name swarm-registrator --net host -v /var/run/docker.sock:/var/run/docker.sock yatheo/swarm_consul_registrator:v0.1 consul://localhost:8500`

Run swarm-registrator as Swarm service:

`docker service create --name swarm-registrator --network host --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock yatheo/swarm_consul_
registrator:v0.1 consul://localhost:8500`
