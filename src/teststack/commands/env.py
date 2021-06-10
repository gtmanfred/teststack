import string

import click
import docker

from teststack import cli


def get_placeholders(value):
    return [name for text, name, spec, conv in string.Formatter().parse(value)]


@cli.command()
@click.pass_context
def export(ctx):
    envvars = []
    client = docker.from_env()
    for service, data in ctx.obj['config'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            continue
        container_data = data['environment'].copy()
        container_data['HOST'] = 'localhost'
        for port, port_data in container.attrs['NetworkSettings']['Ports'].items():
            container_data[f'PORT;{port}'] = port_data[0]['HostPort']
        for key, value in data['export'].items():
            envvars.append(
                f'export {key}={value}'.format_map(
                    container_data,
                )
            )
    print('\n'.join(envvars))
