#!/usr/bin/env python
""" Listen for swarm services and register them in Consul """

import docker
import consul

def main():
    client = docker.from_env()
    for event in client.events(decode=True):
        print(event, "\n")
        if event['Type'] != "service":
            continue
        actor = event['Actor']
        service_id = actor['ID']
        service_name = actor['Attributes']['name']
        c = consul.Consul()
        if event['Action'] == "remove":
            c.kv.delete('http/service/'+service_name, recurse=True)
        elif event['Action'] == 'update':
            service = client.services.get(service_id)
            print('Service', service.attrs)
            endpoints = service.attrs['Endpoint']['Ports']
            published_ports = [x['PublishedPort'] for x in endpoints if 'PublishedPort' in x]
            c.kv.put('http/service/{}/swarm_ports'.format(service_name), str(published_ports[0]))
            # print([x['PublishedPort'] for x in endpoints])
            print(endpoints)

if __name__ == "__main__":
    main()
