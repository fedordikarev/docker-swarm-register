#!/usr/bin/env python
""" Listen for swarm services and register them in Consul """

import json
import argparse
import consul
import docker

REGISTRATOR_PREFIX = "swarm-registrator/v1/http/"
APPSETTINGS_PREFIX = "appsettings/v1/"


def parse_args():
    """ Parse args """
    parser = argparse.ArgumentParser(description='register docker service in Consul')
    parser.add_argument('consul_url')
    return parser.parse_args()

def consul_connect(url):
    """ Connect to Consul by giver URL """
    if not url:
        url = "consul://localhost:8500"
    if not url.startswith("consul://"):
        return None
    url = url[len("consul://"):]
    if ":" in url:
        (host, port) = url.split(":", 1)
    else:
        (host, port) = (url, 8500)
    return consul.Consul(host, port=port)

def main():
    """ Main loop """
    client = docker.from_env()
    args = parse_args()

    for event in client.events(decode=True):
        if event['Type'] != "service":
            continue
        print("DEBUG event:", event, "\n")
        actor = event['Actor']
        service_id = actor['ID']
        service_name = actor['Attributes']['name']
        c = consul_connect(args.consul_url)     #pylint: disable=invalid-name
        if event['Action'] == "remove":
            print("Delete ", REGISTRATOR_PREFIX + service_name)
            c.kv.delete(REGISTRATOR_PREFIX + service_name)
        elif event['Action'] in ('create', 'update'):
            service = client.services.get(service_id)
            settings_from_consul = c.kv.get(APPSETTINGS_PREFIX + service_name)
            if settings_from_consul[1]:
                app_settings = json.loads(settings_from_consul[1].get('Value'))
            else:
                app_settings = {}
            endpoints = service.attrs.get('Endpoint', {}).get('Ports', [])
            published_ports = [x['PublishedPort'] for x in endpoints if 'PublishedPort' in x]
            if published_ports:
                app_settings['swarm_port'] = str(published_ports[0])
                c.kv.put(REGISTRATOR_PREFIX + service_name, json.dumps(app_settings))
            else:
                print(service_name, "created but no PublishedPorts found")
            print(json.dumps(app_settings))

if __name__ == "__main__":
    main()
