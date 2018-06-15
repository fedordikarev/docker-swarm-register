#!/usr/bin/env python
""" Listen for swarm services and register them in Consul """

import json
import argparse
import consul
import docker

REGISTRATOR_PREFIX = "swarm-registrator/v1/http/"
REGISTRATOR_TCP_PREFIX = "swarm-registrator/v1/tcp/"
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
            if endpoints:
                http_port = int(app_settings.get("http_port", endpoints[0]["TargetPort"]))
                tcp_ports = []
                swarm_http_port = None
                for endpoint in endpoints:
                    if endpoint["TargetPort"] == http_port:
                        swarm_http_port = endpoint.get("PublishedPort")
                    elif endpoint.get("PublishedPort"):
                        tcp_ports.append({endpoint.get("PublishedPort"): endpoint.get("TargetPort")})

                if swarm_http_port:
                    app_settings['swarm_port'] = str(swarm_http_port)
                    c.kv.put(REGISTRATOR_PREFIX + service_name, json.dumps(app_settings))
                else:
                    print(service_name, "created but no HTTP PublishedPorts found")

                if tcp_ports:
                    c.kv.put(REGISTRATOR_TCP_PREFIX + service_name, json.dumps(tcp_ports))
                else:
                    c.kv.delete(REGISTRATOR_TCP_PREFIX + service_name)
            else:
                print(service_name, "no endpoints found")


if __name__ == "__main__":
    main()
