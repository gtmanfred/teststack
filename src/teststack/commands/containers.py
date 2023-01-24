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
import os
import sys

import click
import jinja2

from teststack import cli
from teststack.git import get_path


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
    client = ctx.obj.get('client')
    if no_mount is not True:
        no_mount = not ctx.obj.get('tests.mount', True)

    for service, data in ctx.obj.get('services').items():
        if 'import' in data:
            ctx.invoke(import_, **data['import'])
            continue
        name = f'{prefix}{ctx.obj.get("project_name")}_{service}'
        container = client.container_get(name)
        if 'build' in data:
            data['image'] = f'{ctx.obj.get("prefix")}{service}:{ctx.obj.get("commit", "latest")}'
            image = client.image_get(data['image'])
            if image is None:
                ctx.invoke(
                    build,
                    directory=data['build'],
                    tag=data['image'],
                    service=service,
                )
        if container is None:
            click.echo(f'Starting container: {name}')
            client.run(
                image=data['image'],
                ports=data.get('ports', {}),
                name=name,
                command=data.get('command', None),
                environment=data.get('environment', {}),
                mount_cwd=False,
                network=ctx.obj['project_name'],
                service=service,
            )
        else:
            client.start(name=name)

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
    else:
        container = client.container_get(name)

    if current_image_id is None:
        command = ctx.obj.get('tests.command', True)
        if imp is True:
            command = ctx.obj.get('tests.import.command', None)

        container = client.run(
            image=image,
            stream=True,
            name=name,
            environment=env,
            command=command,
            ports=ctx.obj.get('tests.ports', {}),
            mount_cwd=not no_mount,
            network=ctx.obj['project_name'],
        )

        if imp is True:
            for step in ctx.obj.get('tests.import.setup', []):
                client.run_command(
                    container,
                    step,
                )

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
    client = ctx.obj['client']
    project_name = ctx.obj["project_name"]
    for service, data in ctx.obj['services'].items():
        if 'import' in data:
            ctx.invoke(import_, stop=True, **data['import'])
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
                f'RUN echo "app-git-hash: {ctx.obj["commit"]} >> /etc/docker-metadata"',
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
@click.pass_context
def build(ctx, rebuild, tag, dockerfile, template_file, directory, service):
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

    .. code-block:: bash

        teststack build
        teststack build --tag blah:old
    """
    if service:
        if tag is None:
            tag = f'{ctx.obj.get("prefix")}{service}:{ctx.obj.get("commit", "latest")}'
        directory = ctx.obj.get(f'services.{service}.build')
        buildargs = ctx.obj.get(f'services.{service}.buildargs')
    else:
        buildargs = ctx.obj.get(f'tests.buildargs')

    try:
        tempstat = os.stat(os.path.join(directory, template_file))
    except FileNotFoundError:
        tempstat = None

    try:
        dockerstat = os.stat(os.path.join(directory, dockerfile))
    except FileNotFoundError:
        dockerstat = None

    if tempstat is not None and (dockerstat is None or dockerstat.st_mtime < tempstat.st_mtime):
        with open(template_file, 'r') as th_:
            ctx.invoke(render, dockerfile=dockerfile, template_file=th_)

    client = ctx.obj['client']

    if tag is None:
        tag = ctx.obj['tag']

    click.echo(f'Build Image: {tag}')
    client.build(dockerfile, tag, rebuild, directory=directory, buildargs=buildargs)
    image = client.image_get(tag)
    if image is None:
        click.echo(click.style('Failed to build image!', fg='red'))
        sys.exit(11)

    return tag


@cli.command()
@click.pass_context
@click.option('--user', '-u', default=None, nargs=1, type=click.STRING, help='User to exec to the container as')
def exec(ctx, user):  # pragma: no cover
    """
    Exec into the current tests container.

    .. code-block:: bash

        teststack exec
    """
    container = ctx.invoke(start)
    ctx.obj['client'].exec(container, user=user)


@cli.command()
@click.pass_context
def tag(ctx):
    click.echo(ctx.obj['tag'])


def _process_steps(steps):
    """
    Process step information from teststack.toml and convert it to a data blob
    that can be processed in order.
    """
    commands = {}
    for name, command in steps.items():
        cmd = {'user': None}
        if isinstance(command, dict):
            cmd.update(command)
            if 'requires' in cmd:
                for require in cmd['requires']:
                    commands.setdefault(require, {}).setdefault('required_by', set()).add(name)
        else:
            cmd.update({'command': command})
        commands.setdefault(name, {}).update(cmd)
    return commands


def _run(command, user, ctx):
    """
    Run a command in a container.
    """
    if isinstance(command, str):
        command = [command]
    exit_code = 0
    for cmd in command:
        exit_code += ctx['client'].run_command(
            ctx['container'],
            cmd.format(posargs=' '.join(ctx['posargs'])),
            user=user,
        )
    return exit_code


def _do_check(command, ctx):
    """
    Evaluate a the check on a command to see if it needs to be run.
    """
    if 'check_exit_code' in command:
        return command['check_exit_code']

    if 'required_by' in command:
        exit_code = 1
        for required_by in command['required_by']:
            exit_code = _do_check(ctx['commands'][required_by], ctx)
        if not exit_code:
            return exit_code

    if 'check' in command:
        command['check_exit_code'] = _run(command['check'], command['user'], ctx)
        return command['check_exit_code']
    return 1


def _run_command(command, ctx):
    """
    Evaluate a the require and require_by attributes on a command to see if it
    needs to be run.
    """
    if 'exit_code' in command:
        return command['exit_code']

    if 'check' in command:
        command['check_exit_code'] = result = _do_check(command, ctx)
        if not result:
            return 0

    if 'required_by' in command:
        required_by_check = False
        for required_by in command['required_by']:
            cmd = ctx['commands'][required_by]
            if 'exit_code' in cmd:
                continue
            exit_code = _do_check(cmd, ctx)
            if exit_code == 0:
                continue
            required_by_check = True
            break

        if required_by_check is False:
            return 0

    if 'requires' in command:
        requires_exit_code = 0
        for require in command['requires']:
            exit_code = _run_command(ctx['commands'][require], ctx)
            ctx['commands'][require]['exit_code'] = exit_code
            requires_exit_code += exit_code

        if requires_exit_code:
            return requires_exit_code

    return _run(command['command'], command['user'], ctx)


def _run_commands(ctx):
    for command in ctx['commands'].values():
        command['exit_code'] = _run_command(command, ctx)
    return sum([result['exit_code'] for result in ctx['commands'].values()])


@cli.command()
@click.option('--step', '-s', help='Which step to run')
@click.argument('posargs', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(ctx, step, posargs):
    """
    Run the specified test steps from the teststack.toml.

    --step, -s

        specify a single step to run.

    posargs

        All other leftover unprocessed arguments are passed as {posargs} to be
        rendered when the commands.

    .. code-block:: bash

        teststack run
        teststack run --step tests -- -k test_add_user tests/unit/test_users.py
    """
    container = ctx.invoke(start)

    steps = ctx.obj['tests'].get('steps', {})
    if step:
        stepobj = steps.get(step, '{posargs}')
        new_steps = {step: stepobj}
        if 'requires' in stepobj:
            new_steps.update({s: steps[s] for s in stepobj['requires']})
        steps = new_steps
    exit_code = 0
    commands = _process_steps(steps)
    runctx = {'commands': commands, 'container': container, 'posargs': posargs, 'client': ctx.obj['client']}
    exit_code = _run_commands(runctx)
    if exit_code:
        sys.exit(exit_code)


@cli.command()
@click.pass_context
def status(ctx):
    """
    Show status of containers

    .. code-block:: bash

        teststack status
    """
    client = ctx.obj['client']
    click.echo('{:_^16}|{:_^36}|{:_^16}'.format('status', 'name', 'data'))
    network_name = network = ctx.obj['project_name']
    for service, data in ctx.obj['services'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        container = client.get_container_data(name, network_name) or {}
        container.pop('HOST', None)
        click.echo('{:^16}|{:^36}|{:^16}'.format(client.status(name), name, str(container)))
    name = f'{ctx.obj["project_name"]}_tests'
    container = client.get_container_data(name, network_name) or {}
    container.pop('HOST', None)
    click.echo('{:^16}|{:^36}|{:^16}'.format(client.status(name), name, str(container)))


@cli.command(name='import')
@click.option('--repo', '-r', required=True, help='Import and run another repo as a service')
@click.option('--ref', '--tag', '-t', default=None, help='Revision to checkout on a remote repo')
@click.option('--stop', is_flag=True, help='Stop the imported containers instead')
@click.pass_context
def import_(ctx, repo, ref, stop):
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
    path = get_path(repo, ref)
    runner = click.testing.CliRunner()
    if stop is True:
        click.echo(f'Stopping import environment: {path}')
        runner.invoke(
            cli,
            [
                f'--path={path}',
                'stop',
                f'--prefix={ctx.obj.get("project_name")}.',
            ],
        )
    else:
        click.echo(f'Starting import environment: {path}')
        runner.invoke(
            cli,
            [
                f'--path={path}',
                'start',
                '-m',
                '--imp',
                f'--prefix={ctx.obj.get("project_name")}.',
            ],
        )


@cli.command(name='copy')
@click.pass_context
def copy_(ctx):
    client = ctx.obj['client']
    name = f'{ctx.obj.get("project_name")}_tests'
    exit_code = 0
    for src in ctx.obj.get('tests.copy'):
        result = client.cp(name, src)
        if result is False:
            click.echo(click.style(f'Failed to retrieve {src}!', fg='red'))
            exit_code = 12
    if exit_code:
        sys.exit(exit_code)
