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
import os.path
import sys

import click
import jinja2

from teststack import cli


@cli.command()
@click.option('--no-tests', '-n', is_flag=True, help='Don\'t start the tests container')
@click.pass_context
def start(ctx, no_tests):
    """
    Start services and tests containers.

    If the flag ``--no-tests`` is passed, then the tests container is not
    started, and only the services are started. This is useful if running tests
    outside of a docker container.

    --no-tests, -n

        do not build an image or start a tests container

    .. code-block:: bash

        teststack start --no-tests
    """
    client = ctx.obj['client']
    for service, data in ctx.obj['services'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        container = client.container_get(name)
        if container is None:
            container = client.run(
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

    env = ctx.invoke(cli.get_command(ctx, 'env'), inside=True, no_export=True, quiet=True)
    env = dict(line.split('=') for line in env)
    image = client.image_get(ctx.obj['tag'])
    if image is None:
        image = client.image_get(ctx.invoke(build))

    name = f'{ctx.obj["project_name"]}_tests'

    current_image_id = client.container_get_current_image(name)
    if current_image_id != image:
        client.end_container(name)
        current_image_id = None
    else:
        container = client.container_get(name)

    if current_image_id is None:
        command = ctx.obj['tests'].get('command', True)

        container = client.run(
            image=image,
            stream=True,
            name=name,
            user=0,
            environment=env,
            command=command,
            mount_cwd=True,
        )

    return container


@cli.command()
@click.pass_context
def stop(ctx):
    """
    Stop all containers

    .. code-block:: bash

        teststack stop
    """
    client = ctx.obj['client']
    project_name = ctx.obj["project_name"]
    for service, _ in ctx.obj['services'].items():
        name = f'{project_name}_{service}'
        container = client.container_get(name)
        if container is None:
            continue
        client.end_container(container)
    container = client.container_get(f'{project_name}_tests')
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
        GIT_BRANCH=ctx.obj.get('branch', 'dev'),
        GIT_COMMIT_HASH=ctx.obj.get('commit', None),
        **os.environ,
    ).dump(dockerfile)


@cli.command()
@click.option('--rebuild', '-r', is_flag=True, help='ignore cache and rebuild the container fully')
@click.option('--tag', '-t', default=None, help='Tag to label the build')
@click.option(
    '--dockerfile', '--file', '-f', type=click.Path(), default='Dockerfile', help='container build file to write too'
)
@click.option('--template-file', type=click.Path(), default='Dockerfile.j2', help='template to render with jinja')
@click.pass_context
def build(ctx, rebuild, tag, dockerfile, template_file):
    """
    Build the docker image using the dockerfile.

    If the dockerfile does not exist, then it will be rendered.

    --template-file

        Template to render to the Dockerfile

    --dockerfile, --file, -f

        dockerfile to build into an image. Default: Dockerfile

    --rebuild, -r

        Ignore the cache and rebuild from scratch

    --tag, -t

        Tag to use for the image.  Default: <dirname>:<latest git hash/"latest">

    .. code-block:: bash

        teststack build
        teststack build --tag blah:old
    """
    try:
        tempstat = os.stat(template_file)
    except FileNotFoundError:
        tempstat = None

    try:
        dockerstat = os.stat(dockerfile)
    except FileNotFoundError:
        dockerstat = None

    if tempstat is not None and (dockerstat is None or dockerstat.st_mtime < tempstat.st_mtime):
        with open(template_file, 'r') as th_:
            ctx.invoke(render, dockerfile=dockerfile, template_file=th_)

    client = ctx.obj['client']

    if tag is None:
        tag = ctx.obj['tag']

    click.echo(f'Build Image: {tag}')
    client.build(dockerfile, tag, rebuild)
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
    for command in commands:
        if isinstance(command, list):
            for cmd in command:
                client.run_command(container, cmd.format(posargs=' '.join(posargs)))
        else:
            client.run_command(container, command.format(posargs=' '.join(posargs)))
