import string

import click
import docker

from teststack import cli


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
    """
    envvars = []
    client = ctx.obj['client']
    for service, data in ctx.obj['services'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
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
    for key, value in ctx.obj['tests'].get('environment', {}).items():
        envvars.append(f'{"" if no_export else "export "}{key}={value}')
    if quiet is False:
        click.echo('\n'.join(envvars))
    return envvars
