import string

import click
import docker

from teststack import cli


def get_placeholders(value):
    return [name for text, name, spec, conv in string.Formatter().parse(value)]


@cli.command()
@click.option(
    '--no-export',
    '-n',
    is_flag=True,
    default=False,
    help='do not include the export command with environment variables',
)
@click.option('--inside', is_flag=True, default=False, help='Export variables for inside a docker container')
@click.option('--quiet', '-q', is_flag=True, help='Do not print out information')
@click.pass_context
def env(ctx, no_export, inside, quiet):
    envvars = []
    client = docker.from_env()
    for service, data in ctx.obj['config'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            continue
        container_data = data['environment'].copy()
        container_data['HOST'] = container.attrs['NetworkSettings']['IPAddress'] if inside else 'localhost'
        for port, port_data in container.attrs['NetworkSettings']['Ports'].items():
            container_data[f'PORT;{port}'] = port.split('/')[0] if inside else port_data[0]['HostPort']
        for key, value in data['export'].items():
            envvars.append(
                f'{"" if no_export else "export "}{key}={value}'.format_map(
                    container_data,
                )
            )
    if quiet is False:
        click.echo('\n'.join(envvars))
    return envvars
