import sys
import subprocess

import click

from teststack import cli
from teststack.git import get_path


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
@click.option('--prefix', default='', help='Prefix name of containers for import')
@click.pass_context
def env(ctx, no_export, inside, quiet, prefix):
    """
    Output the environment variables for the teststack environment.

    --no-export, -n

        Do not prefix each line with export, this is good for making .env files for
        stuff like VSCode

    --inside

        export HOST and PORT values for inside of the containers. This is used
        to set the environment variables in the ``tests`` container.

    --quiet, -q

        Do not print anything out, just return the environment variables. This
        is for internal use so that the variables are not printed out when
        called inside teststack

    --prefix

        Prefixed name of containers for getting env from imports
    """
    envvars = []
    client = ctx.obj.get('client')
    for service, data in ctx.obj.get('services').items():
        if 'import' in data:
            path = get_path(**data['import'])
            cmd = [
                sys.executable,
                '-m',
                'teststack',
                f'--path={path}',
                'import-env',
                f'--prefix={ctx.obj.get("project_name")}.',
            ]
            if no_export is True:
                cmd.append('--no-export')
            if inside is True:
                cmd.append('--inside')
            result = subprocess.run(cmd, stdout=subprocess.PIPE)
            envvars.extend(result.stdout.decode('utf-8').strip('\n').split('\n'))
            continue
        name = f'{prefix}{ctx.obj.get("project_name")}_{service}'
        container_data = client.get_container_data(name, inside=inside)
        if container_data is None:
            continue
        container_data.update(data.get('environment', {}).copy())
        for key, value in data.get('export', {}).items():
            envvars.append(
                f'{"" if no_export else "export "}{key}={value}'.format_map(
                    container_data,
                )
            )
    name = f'{ctx.obj.get("project_name")}_tests'
    container_data = client.get_container_data(name, inside=inside)
    if container_data is not None:
        for key, value in ctx.obj.get('tests.environment', {}).items():
            envvars.append(
                f'{"" if no_export else "export "}{key}={value}'.format_map(
                    container_data,
                )
            )
    else:
        for key, value in ctx.obj.get('tests.environment', {}).items():
            envvars.append(f'{"" if no_export else "export "}{key}={value}')
    if quiet is False:
        click.echo('\n'.join(envvars))
    return envvars


@cli.command(name='import-env')
@click.option(
    '--no-export',
    '-n',
    is_flag=True,
    default=False,
    help='do not include the export command with environment variables',
)
@click.option('--inside', is_flag=True, default=False, help='Export variables for inside a docker container')
@click.option('--prefix', default='', help='Prefix name of containers for import')
@click.pass_context
def import_env(ctx, no_export, inside, prefix):
    envvars = []
    client = ctx.obj['client']
    name = f'{prefix}{ctx.obj.get("project_name")}_tests'
    container_data = client.get_container_data(name, inside=inside)
    if container_data is not None:
        for key, value in ctx.obj.get('tests.environment', {}).items():
            envvars.append(
                f'{"" if no_export else "export "}{key}={value}'.format_map(
                    container_data,
                )
            )
    else:
        for key, value in ctx.obj.get('tests.environment', {}).items():
            envvars.append(f'{"" if no_export else "export "}{key}={value}')
    click.echo('\n'.join(envvars))
