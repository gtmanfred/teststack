import click.testing
from teststack import cli
from teststack.configuration import Service
from teststack.configuration import Tests
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
def env(ctx, no_export: bool, inside: bool, quiet: bool, prefix: str) -> list[str]:
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
    tests: Tests = ctx.obj['tests']
    service: str
    data: Service
    for service, data in ctx.obj.get('services').items():
        if data.import_ is not None:
            path = get_path(repo=data.import_.repo, ref=data.import_.ref)
            args = [
                f'--path={path}',
                'import-env',
                f'--prefix={ctx.obj.get("project_name")}.',
            ]
            if no_export is True:
                args.append('--no-export')
            if inside is True:
                args.append('--inside')
            runner = click.testing.CliRunner()
            result = runner.invoke(cli, args)
            envvars.extend([line for line in result.stdout.strip('\n').split('\n') if line])
            continue
        name = f'{prefix}{ctx.obj.get("project_name")}_{service}'
        container_data = client.get_container_data(name, network=ctx.obj['project_name'], inside=inside)
        if container_data is None:
            continue
        container_data.update(data.environment.copy())
        for key, value in data.export.items():
            envvars.append(
                f'{"" if no_export else "export "}{key}={value}'.format_map(
                    container_data,
                )
            )
    name = f'{ctx.obj.get("project_name")}_tests'
    container_data = client.get_container_data(name, network=ctx.obj['project_name'], inside=inside)
    if container_data is not None:
        for key, value in tests.environment.items():
            envvars.append(
                f'{"" if no_export else "export "}{key}={value}'.format_map(
                    container_data,
                )
            )
    else:
        for key, value in tests.environment.items():
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
def import_env(ctx, no_export: bool, inside: bool, prefix: str) -> None:
    envvars = []
    client = ctx.obj['client']
    tests: Tests = ctx.obj['tests']
    name = f'{prefix}{ctx.obj.get("project_name")}_tests'
    container_data = client.get_container_data(name, network=ctx.obj['project_name'], inside=inside)
    if container_data is not None:
        for key, value in tests.export.items():
            envvars.append(
                f'{"" if no_export else "export "}{key}={value}'.format_map(
                    container_data,
                )
            )
    else:
        for key, value in tests.export.items():
            envvars.append(f'{"" if no_export else "export "}{key}={value}')
    click.echo('\n'.join(envvars))
