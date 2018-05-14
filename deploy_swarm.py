#!/usr/bin/env python
""" Deploy service to Docker Swarm or Update one if already deployed """

import collections
import pprint
import argparse
import json
import yaml
import consul
import docker
import jinja2

KV_PREFIX = "appsettings/v1/"
FS_PATH = "/local/innova/tools/inn-swarm-deploy"

def dict_merge(dct, merge_dct):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.items():      #pylint: disable=invalid-name,unused-variable
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.Mapping)):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]

def parse_args():
    """ Parse cli arguments """
    parser = argparse.ArgumentParser(description='deploy or update service')
    parser.add_argument("--env", help="deploy environment", default="qa")
    parser.add_argument("--name", help="service name")
    parser.add_argument("--appsettings", help="appsettings.json file")
    parser.add_argument("image", help="image", default="yahteo/swarm-docker-demo:latest")
    return parser.parse_args()

def read_env(name):
    """ Read environment description """
    with open(FS_PATH+"/conf/{}.yaml".format(name), "r") as f:  #pylint: disable=invalid-name
        return yaml.load(f)

def guess_name_from_image(image_name):
    """ Guess service name from image name """
    base_name = image_name.split("/")[-1]
    return base_name.split(":", 1)[0]

def consul_connect(url):
    """ Connect to Consul by given URL """
    if not url:
        url = "localhost:8500"
    if ":" in url:
        (host, port) = url.split(":", 1)
    else:
        (host, port) = (url, 8500)
    return consul.Consul(host, port=port)

def read_appsettings(filename, env, service_name):
    """ Read and render appsettings.json """
    if filename.startswith("/"):
        loader = jinja2.FileSystemLoader('/')
    else:
        loader = jinja2.FileSystemLoader('.')
    jinja_env = jinja2.Environment(loader=loader)
    settings_template = jinja_env.get_template(filename)
    settings = settings_template.render(service_name=service_name, env=env)
    app_settings = json.loads(settings)
    return app_settings

def main():
    """ Main action """
    #TODO: Refactor this function later
    args = parse_args()
    env = read_env(args.env)
    if 'swarm' in env:
        d = docker.DockerClient(base_url=env['swarm'])  #pylint: disable=invalid-name
    else:
        d = docker.from_env()   #pylint: disable=invalid-name
    if args.name:
        service_name = args.name
    else:
        service_name = guess_name_from_image(args.image)
        print("Guess {}".format(service_name))

    app_settings = read_appsettings(FS_PATH+'/conf/default_app.json',
                                    env=env, service_name=service_name)
    if args.appsettings:
        dict_merge(
            app_settings,
            read_appsettings(args.appsettings, env=env, service_name=service_name)
            )

    pprint.pprint(app_settings)

    print("Name: {}".format(service_name))
    try:
        serv = d.services.get(service_name)
    except docker.errors.NotFound:
        serv = None
    if serv:
        print("Update service {}".format(service_name))
        update_config = docker.types.UpdateConfig(order="start-first")
        serv.update(image=args.image, update_config=update_config)
    else:
        print("Create service {}".format(service_name))
        port = app_settings['deployment'].get("containerport", 5000)
        c = consul_connect(env['consul'])   #pylint: disable=invalid-name
        c.kv.put(KV_PREFIX + service_name, json.dumps(app_settings['url']))
        endports = {"Mode": "vip", "Ports": [{"Protocol": "tcp", "TargetPort": int(port)}]}
        replica_mode = docker.types.ServiceMode(
            'replicated',
            replicas=int(app_settings['deployment'].get("instances", "1"))
            )
        if 'cpu_limit' in app_settings['deployment']:
            cpu_limit = int(1e9 * float(app_settings['deployment']['cpu_limit']))
        else:
            cpu_limit = None
        if 'mem_limit' in app_settings['deployment']:
            muls = {'k': 1024, 'K': 1024,
                    'm': 1024 ** 2, 'M': 1024 ** 2,
                    'g': 1024 ** 3, 'G': 1024 ** 3}
            mem_limit = app_settings['deployment']['mem_limit']
            if mem_limit[-1] in muls:
                mem_limit = int(mem_limit[:-1]) * muls[mem_limit[-1]]
            else:
                mem_limit = int(mem_limit)
        else:
            mem_limit = None
        resources = docker.types.Resources(
            cpu_limit=cpu_limit,
            mem_limit=mem_limit
            )
        d.services.create(
            args.image,
            name=service_name,
            endpoint_spec=endports,
            env=app_settings['env'],
            mode=replica_mode,
            resources=resources,
            mounts=app_settings.get("volumes", [])
            )

if __name__ == "__main__":
    main()
