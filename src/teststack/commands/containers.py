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
def exec(ctx):  # pragma: no cover
    """
    Exec into the current tests container.

    .. code-block:: bash

        teststack exec
    """
    container = ctx.invoke(start)
    ctx.obj['client'].exec(container)


@cli.command()
@click.pass_context
def tag(ctx):
    click.echo(ctx.obj['tag'])


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
    client = ctx.obj['client']

    steps = ctx.obj['tests'].get('steps', {})
    if step:
        commands = [steps.get(step, '{posargs}')]
    else:
        commands = steps.values()
    exit_code = 0
    for command in commands:
        user = None
        if isinstance(command, list):
            for cmd in command:
                if isinstance(cmd, dict):
                    cmd, user = cmd['command'], cmd.get('user')
                ret = client.run_command(
                    container,
                    cmd.format(posargs=' '.join(posargs)),
                    user=user,
                )
                if ret:
                    exit_code = ret
        elif isinstance(command, dict):
            cmd, user = command['command'], command['user']

            ret = client.run_command(
                container,
                cmd.format(posargs=' '.join(posargs)),
                user=user,
            )
        else:
            ret = client.run_command(container, command.format(posargs=' '.join(posargs)))
        if ret:
            exit_code = ret
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
    for service, data in ctx.obj['services'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        container = client.get_container_data(name) or {}
        container.pop('HOST', None)
        click.echo('{:^16}|{:^36}|{:^16}'.format(client.status(name), name, str(container)))
    name = f'{ctx.obj["project_name"]}_tests'
    container = client.get_container_data(name) or {}
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
