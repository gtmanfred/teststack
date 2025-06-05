"""
The containers related commands handle the majority of the work that teststack does.

The work is abstracted into the different container drivers.  You can specify
which container driver to use in the ``teststack.toml`` file.

.. code-block:: toml

    [client]
    name = "docker"

All of the commands can be combined together and they will be executed in order.
So if for example you want to rebuild the image without any cache and then run
the tests you could do the following.

.. code-block::

    teststack build --rebuild run
"""
import logging
import os
import sys
from collections import OrderedDict
from dataclasses import dataclass

import click
import jinja2
from teststack import cli
from teststack.configuration import Service
from teststack.configuration import Tests
from teststack.configuration.tests import Step
from teststack.containers import Client
from teststack.git import get_path

logger = logging.getLogger(__name__)


@dataclass
class Command(Step):
    exit_code: int | None = None
    check_exit_code: int | None = None
    required_by: set[str] | None = None


@cli.command()
@click.option('--no-tests', '-n', is_flag=True, help='Don\'t start the tests container')
@click.option('--no-mount', '-m', is_flag=True, help='Don\'t mount the current directory')
@click.option('--imp', '-i', is_flag=True, help='Start container as an import')
@click.option('--prefix', '-p', default='', help='Prefix to start a container name with')
@click.pass_context
def start(ctx, no_tests, no_mount, imp, prefix):
    """
    Start services and tests containers.

    If the flag ``--no-tests`` is passed, then the tests container is not
    started, and only the services are started. This is useful if running tests
    outside of a docker container.

    --no-tests, -n

        do not build an image or start a tests container

    --no-mount, -m

        do not mount the current directory as a volume

    .. code-block:: bash

        teststack start --no-tests
    """
    logger.debug(f"Invoking 'start', --no-tests {no_tests}, --no-mount {no_mount}, --imp {imp}, --prefix {prefix}")

    # Imports should not mount the current directory, or start test containers
    if imp:
        no_tests = True
        no_mount = True

    client: Client = ctx.obj.get('client')
    tests: Tests = ctx.obj.get('tests')

    if no_mount is not True:
        no_mount = not tests.mount

    service: str
    data: Service
    for service, data in ctx.obj.get('services').items():
        logger.debug(f"Starting {service}: {data}")
        if data.import_ is not None:
            ctx.invoke(import_, repo=data.import_.repo, ref=data.import_.ref)
            continue
        name = f'{prefix}{ctx.obj.get("project_name")}_{service}'
        if data.build is not None:
            data.image = f'{ctx.obj.get("prefix")}{service}:{ctx.obj.get("commit", "latest")}'
            image = client.image_get(data.image)
            if image is None:
                ctx.invoke(
                    build,
                    directory=data.build,
                    tag=data.image,
                    service=service,
                )
        container = client.container_get(name)
        if container is None:
            click.echo(f'Starting container: {name}')
            mounts = data.mounts
            logger.debug("Container Mounts: {mounts}")
            volumes = {}
            if mounts:
                for mount in mounts.values():
                    volumes.update(
                        {
                            os.path.expanduser(mount.source): {
                                "bind": mount.target,
                                "mode": mount.mode,
                            }
                        }
                    )
            client.run(
                image=data.image,
                ports=data.ports,
                name=name,
                command=data.command,
                environment=data.environment,
                mount_cwd=False,
                network=ctx.obj['project_name'],
                service=service,
                volumes=volumes,
            )
        else:
            client.start(name=name)

        if client.status(name) != "running":
            click.echo(f'Failed to start container for {service}')
            click.echo(client.logs(name))
            raise click.Abort

    if no_tests is True:
        return

    env = ctx.invoke(cli.get_command(ctx, 'env'), prefix=prefix, inside=True, no_export=True, quiet=True)
    env = dict(line.split('=') for line in env)
    image = client.image_get(ctx.obj['tag'])
    if image is None:
        image = client.image_get(ctx.invoke(build))

    name = f'{prefix}{ctx.obj.get("project_name")}_tests'

    current_image_id = client.container_get_current_image(name)
    if current_image_id != image:
        client.end_container(name)
        current_image_id = None
        logger.debug("Test Container Outdated. Restarting")

    if current_image_id is None:
        click.echo(f'Starting container: {name}')

        command = tests.command
        if imp is True:
            command = tests._import.command

        # Looks like all code currently supported containerization engines use a tail, so use that if command is None
        if command is None:
            command = "-c 'trap \"trap - TERM; kill -s TERM -- -$$\" TERM; tail -f /dev/null & wait'"

        mounts = tests.mounts
        logger.debug("Test Mounts: {mounts}")
        volumes = {}
        if mounts:
            for mount in mounts.values():
                volumes.update(
                    {
                        os.path.expanduser(mount.source): {
                            "bind": mount.target,
                            "mode": mount.mode,
                        }
                    }
                )
        container = client.run(
            image=image,
            stream=True,
            name=name,
            environment=env,
            command=command,
            ports=tests.ports,
            mount_cwd=not no_mount,
            network=ctx.obj['project_name'],
            volumes=volumes,
        )

        if imp is True:
            for step in tests._import.setup:
                client.run_command(
                    container,
                    step,
                )
    else:
        container = client.container_get(name)
        logger.debug(f"Found Test Container {name}:{container}")

    return container


@cli.command()
@click.option('--prefix', '-p', default='', help='Prefix to start a container name with')
@click.pass_context
def stop(ctx, prefix):
    """
    Stop all containers

    --prefix, -p

        prefix for container names for imports

    .. code-block:: bash

        teststack stop
    """
    client: Client = ctx.obj['client']
    project_name = ctx.obj["project_name"]
    service: str
    data: Service
    for service, data in ctx.obj['services'].items():
        if data.import_ is not None:
            ctx.invoke(import_, stop=True, repo=data.import_.repo, ref=data.import_.ref)
            continue
        name = f'{prefix}{project_name}_{service}'
        container = client.container_get(name)
        if container is None:
            continue
        click.echo(f'Stopping container: {name}')
        client.end_container(container)
    container = client.container_get(f'{prefix}{project_name}_tests')
    if container is None:
        return
    client.end_container(container)
    if hasattr(client, 'network_prune'):
        client.network_prune()


@cli.command()
@click.pass_context
def restart(ctx):  # pragma: no cover
    """
    Stop then Start all containers

    .. code-block:: bash

        teststack restart
    """
    ctx.invoke(stop)
    ctx.invoke(start)


@cli.command()
@click.option(
    '--template-file',
    '-t',
    type=click.File(),
    default='Dockerfile.j2',
    help='template to render with jinja',
)
@click.option(
    '--dockerfile', '--file', '-f', type=click.Path(), default='Dockerfile', help='container build file to write to'
)
@click.pass_context
def render(ctx, template_file, dockerfile):
    """
    Render the template_file to the dockerfile.

    --template-file, -t

        template file to render, default: Dockerfile.j2

    --dockerfile, --file, -f

        file to write the rendered dockerfile to. default: Dockerfile

    .. code-block:: bash

        teststack render
        teststack render --template-file Containerfile.j2 --file Containerfile
    """
    env = jinja2.Environment(
        extensions=[
            'jinja2.ext.i18n',
            'jinja2.ext.do',
            'jinja2.ext.loopcontrols',
        ],
        keep_trailing_newline=True,
        undefined=jinja2.Undefined,
        loader=jinja2.FileSystemLoader(os.getcwd()),
    )

    template_string = template_file.read()

    if 'commit' in ctx.obj:
        template_string = '\n'.join(
            [
                template_string,
                f'ENV APP_GIT_HASH={ctx.obj["commit"]}\n',
            ]
        )

    template = env.from_string(
        '\n'.join(
            [
                template_string,
            ]
        ),
    )
    template.stream(
        **{
            'GIT_BRANCH': ctx.obj.get('branch', 'dev'),
            'GIT_COMMIT_HASH': ctx.obj.get('commit', None),
            **os.environ,
        }
    ).dump(dockerfile)


@cli.command()
@click.option('--rebuild', '-r', is_flag=True, help='ignore cache and rebuild the container fully')
@click.option('--tag', '-t', default=None, help='Tag to label the build')
@click.option(
    '--dockerfile', '--file', '-f', type=click.Path(), default='Dockerfile', help='container build file to write too'
)
@click.option('--template-file', type=click.Path(), default='Dockerfile.j2', help='template to render with jinja')
@click.option('--directory', type=click.Path(), default='.', help='Directory to build in')
@click.option('--service', help='Service to build image for')
@click.option('--stage', help='Stage to build in the Dockerfile', default=None)
@click.pass_context
def build(ctx, rebuild, tag, dockerfile, template_file, directory, service, stage):
    """
    Build the docker image using the dockerfile.

    If the dockerfile does not exist, then it will be rendered.

    --template-file

        Template to render to the Dockerfile

    --dockerfile, --file, -f

        dockerfile to build into an image. Default: Dockerfile

    --directory, -d

        directory to build inside. Default: .

    --rebuild, -r

        Ignore the cache and rebuild from scratch

    --tag, -t

        Tag to use for the image.  Default: <dirname>:<latest git hash/"latest">

    --service

        Service specified with a ``build`` argument to build the image for.

    --stage

        Stage to build in the Dockerfile, if specified. Default: None

    .. code-block:: bash

        teststack build
        teststack build --tag blah:old
    """
    logger.debug(
        f"Invoked build: --rebuild {rebuild}, --service {service}, --tag {tag}, "
        f"--dockerfile {dockerfile}, --template-file {template_file}, --directory {directory}, --stage {stage}"
    )
    if service:
        try:
            data: Service = ctx.obj.get('services')[service]
        except KeyError:
            click.echo("Service {service} is not defined", err=True)
            sys.exit(11)
        if tag is None:
            tag = f'{ctx.obj.get("prefix")}{service}:{ctx.obj.get("commit", "latest")}'
        directory = data.build
        buildargs = data.buildargs
        secrets = {name: mount for name, mount in data.mounts.items() if mount.secret is True} if data.mounts else {}
    else:
        tests: Tests = ctx.obj.get('tests')
        buildargs = tests.buildargs
        secrets = {name: mount for name, mount in tests.mounts.items() if mount.secret is True} if tests.mounts else {}

        if stage is None:
            stage = tests.stage

    try:
        tempstat = os.stat(os.path.join(directory, template_file))
    except FileNotFoundError:
        tempstat = None

    try:
        dockerstat = os.stat(os.path.join(directory, dockerfile))
    except FileNotFoundError:
        dockerstat = None

    if tempstat is not None and (dockerstat is None or dockerstat.st_mtime < tempstat.st_mtime):
        with open(template_file) as th_:
            ctx.invoke(render, dockerfile=dockerfile, template_file=th_)

    client: Client = ctx.obj['client']

    if tag is None:
        tag: str = ctx.obj['tag']

    click.echo(f'Build Image: {tag}')
    client.build(
        dockerfile,
        tag,
        rebuild,
        directory=directory,
        buildargs=buildargs,
        secrets=secrets,
        stage=stage,
    )
    image = client.image_get(tag)
    if image is None:
        click.echo(click.style('Failed to build image!', fg='red'))
        sys.exit(11)

    return tag


@cli.command()
@click.pass_context
@click.option('--user', '-u', default=None, nargs=1, type=click.STRING, help='User to exec to the container as')
@click.argument('command', nargs=-1, type=click.UNPROCESSED)
def exec(ctx, user: str | None, command: bytes | str | None):  # pragma: no cover
    """
    Exec into the current tests container.

    .. code-block:: bash

        teststack exec
    """
    container = ctx.invoke(start)
    client: Client = ctx.obj['client']
    client.exec(container, user=user, command=command or None)


@cli.command()
@click.pass_context
def tag(ctx):
    tag: str = ctx.obj['tag']
    click.echo(tag)


def _process_steps(steps: dict[str, Step]) -> OrderedDict[str, Command]:
    """
    Convert the steps into a set of commands
    """
    commands: OrderedDict[str, Command] = {}
    # Build up the reverse relationship of steps a step is required by
    required_by: dict[str, set[str]] = {}
    for name, step in steps.items():
        for required_step in step.requires:
            required_by.setdefault(required_step, set()).add(name)
    for name, step in steps.items():
        commands[name] = Command(
            name=step.name,
            command=step.command,
            requires=step.requires,
            user=step.user,
            required_by=required_by.get(name, None),
            check=step.check,
        )
    return commands


def _run(command: str | list[str], user: str, ctx):
    """
    Run a command in a container.

    Run the command(s), add the exit codes together. If there were no errors, result should be 0
    """
    client: Client = ctx['client']
    if isinstance(command, str):
        command = [command]
    exit_code = 0
    for cmd in command:
        exit_code += client.run_command(
            ctx['container'],
            cmd.format(posargs=' '.join(ctx['posargs'])),
            user=user,
        )
    return exit_code


def _do_check(command: Command, ctx: dict) -> int:
    """
    Evaluate a the check on a command to see if it needs to be run.

    Attempt at plain english:

    - If the check was already run, don't run it again (This is required because of the spaghetti logic)

    - If the step is required by other steps.
        - Regress for each of those steps
        - If the last exit_code is falsely (zero) return it without running this command's check
    ^ This whole chunk seems like a bug.

    - If there is a check (ignoring we really shouldn't call a function named 'do_check' if there's no fucking check)
        - Run the check and record the exit code

    Return 1

    """
    if command.check_exit_code is not None:
        return command.check_exit_code

    if command.required_by:
        exit_code = 1
        for required_by in command.required_by:
            exit_code = _do_check(ctx['commands'][required_by], ctx)
        if not exit_code:
            return exit_code

    if command.check:
        command.check_exit_code = _run(command.check, command.user, ctx)
        return command.check_exit_code
    return 1


def _run_command(command: Command, ctx) -> int:
    """
    Evaluate a the require and require_by attributes on a command to see if it
    needs to be run.

    Attempt at plain english:

    - If the step was already run return the exit code. (This is required because of the spaghetti logic)

    - If the step has a check, run it. (Ignoring the bs in do_check)
        - If the exit code is falsey (zero) return 0......
            - So if the check passes, don't run the command???
    """
    if command.exit_code is not None:
        return command.exit_code

    if command.check:
        result = _do_check(command, ctx)
        if not result:
            return 0

    if command.required_by:
        required_by_check = False
        for required_by in command.required_by:
            cmd = ctx['commands'][required_by]
            if cmd.exit_code is not None:
                continue
            exit_code = _do_check(cmd, ctx)
            if exit_code == 0:
                continue
            required_by_check = True
            break

        if required_by_check is False:
            return 0

    if command.requires:
        requires_exit_code = 0
        for require in command.requires:
            exit_code = _run_command(ctx['commands'][require], ctx)
            requires_exit_code += exit_code

        if requires_exit_code:
            return requires_exit_code

    command.exit_code = _run(command.command, command.user, ctx)
    return command.exit_code


def _run_commands(ctx):
    commands: dict[str, Command] = ctx['commands']
    for command in commands.values():
        command.exit_code = _run_command(command, ctx)
    return sum([result.exit_code for result in ctx['commands'].values()])


@cli.command()
@click.option('--step', '-s', help='Which step to run')
@click.option(
    '--copy',
    '-c',
    is_flag=True,
    default=False,
    help='Copy files out of the container after all the steps have been run',
)
@click.argument('posargs', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(ctx, step: str, copy: bool, posargs):
    """
    Run the specified test steps from the teststack.toml.

    --copy, -c

        Copy files from [tests.copy] out of the container after the steps have been run

    --step, -s

        specify a single step to run.

    posargs

        All other leftover unprocessed arguments are passed as {posargs} to be
        rendered when the commands.

    .. code-block:: bash

        teststack run
        teststack run --step tests -- -k test_add_user tests/unit/test_users.py
    """
    logger.debug(f"Invoking 'run', --copy {copy}, --step {step}, posargs: {posargs}")

    # Load the steps to run
    tests: Tests = ctx.obj['tests']
    logger.debug(f"Test steps: {tests}")
    steps = tests.steps
    if step:
        if step not in steps:
            click.echo(f"{step} is not an available step", err=True)
            sys.exit(1)
        stepobj = steps[step]
        new_steps = OrderedDict({step: stepobj})
        if stepobj.requires is not None:
            new_steps.update({s: steps[s] for s in stepobj.requires})
        steps = new_steps
    commands = _process_steps(steps)
    logger.debug(f"Resolved commands: {commands}")

    # Start up the containers
    container = ctx.invoke(start)

    # Execute the steps
    runctx = {'commands': commands, 'container': container, 'posargs': posargs, 'client': ctx.obj['client']}
    exit_code = _run_commands(runctx)
    if exit_code:
        sys.exit(exit_code)

    # Copy out data
    if copy is True:
        ctx.invoke(copy_)


@cli.command()
@click.pass_context
def status(ctx):
    """
    Show status of containers

    .. code-block:: bash

        teststack status
    """
    client: Client = ctx.obj['client']
    network_name: str = ctx.obj['project_name']
    services: dict[str, Service] = ctx.obj['services']

    click.echo('{:_^16}|{:_^36}|{:_^16}'.format('status', 'name', 'data'))
    # Service Containers
    name: str
    service: Service
    for name, service in services.items():
        if service.import_ is not None:
            continue
        full_name = f'{ctx.obj["project_name"]}_{name}'
        container = client.get_container_data(full_name, network_name) or {}
        container.pop('HOST', None)
        click.echo(f'{client.status(full_name):^16}|{full_name:^36}|{str(container):^16}')
    # Test Container
    full_name = f'{ctx.obj["project_name"]}_tests'
    container = client.get_container_data(full_name, network_name) or {}
    container.pop('HOST', None)
    click.echo(f'{client.status(full_name):^16}|{full_name:^36}|{str(container):^16}')


@cli.command(name='import')
@click.option('--repo', '-r', required=True, help='Import and run another repo as a service')
@click.option('--ref', '--tag', '-t', default=None, help='Revision to checkout on a remote repo')
@click.option('--stop', is_flag=True, help='Stop the imported containers instead')
@click.pass_context
def import_(ctx, repo: str, ref: str | None, stop: bool):
    """
    Load up another repo or directory as a dependency service

    --repo, -r

        Repository or path to directory for application. Urls have to be
        cloneable with git. But paths can be whatever as long as they are on the
        filesystem.

    --ref, --tag, -t

        Git reference to checked out after cloning. Only used if a remote
        repository is specified

    --stop

        stop the containers in the imported environment instead

    .. code-block:: bash

        teststack import --repo ./path
        teststack import --repo ssh://github.com/org/repo.git
    """
    logging.debug(f"Invoking 'import', --repo {repo}, --ref {ref}, --stop {stop}")
    path = get_path(repo, ref)
    runner = click.testing.CliRunner()
    if stop is True:
        click.echo(f'Stopping import environment: {path}')
        result = runner.invoke(
            cli,
            [
                f'--path={path}',
                'stop',
                f'--prefix={ctx.obj.get("project_name")}.',
            ],
            catch_exceptions=False,
        )
        click.echo(result.output)
    else:
        click.echo(f'Starting import environment: {path}')
        result = runner.invoke(
            cli,
            [
                f'--path={path}',
                'start',
                '--imp',
                f'--prefix={ctx.obj.get("project_name")}.',
            ],
            catch_exceptions=False,
        )
        click.echo(result.output)


@cli.command(name='copy')
@click.pass_context
def copy_(ctx):
    client: Client = ctx.obj['client']
    name = f'{ctx.obj.get("project_name")}_tests'
    exit_code = 0
    tests: Tests = ctx.obj['tests']
    for src in tests.copy:
        result = client.cp(name, src)
        if result is False:
            click.echo(click.style(f'Failed to retrieve {src}!', fg='red'))
            exit_code = 12
    if exit_code:
        sys.exit(exit_code)
