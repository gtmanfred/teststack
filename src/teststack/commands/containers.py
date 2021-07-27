import json
import os.path

import click
import docker.errors
import jinja2

from teststack import cli


@cli.command()
@click.option('--no-tests', '-n', is_flag=True, help='Don\'t start the tests container')
@click.pass_context
def start(ctx, no_tests):
    client = docker.from_env()
    for service, data in ctx.obj['services'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            client.containers.run(
                image=data['image'],
                ports=data.get('ports', {}),
                detach=True,
                name=name,
                environment=data.get('environment', {}),
            )

    if no_tests is True:
        return

    env = ctx.invoke(cli.get_command(ctx, 'env'), inside=True, no_export=True, quiet=True)
    try:
        image = client.images.get(ctx.obj['tag'])
    except docker.errors.ImageNotFound:
        image = client.images.get(ctx.invoke(build))

    name = f'{ctx.obj["project_name"]}_tests'
    try:
        container = client.containers.get(name)
        if container.image.id != image.id:
            end_container(container)
            raise docker.errors.NotFound(message='Old Image')
    except docker.errors.NotFound:

        command = ctx.obj['tests'].get('command', None)
        if command is None:  # pragma: no branch
            command = "sh -c 'trap \"trap - TERM; kill -s TERM -- -$$\" TERM; tail -f /dev/null & wait'"

        container = client.containers.run(
            image=image,
            stream=True,
            name=name,
            user=0,
            environment=env,
            command=command,
            detach=True,
            volumes={
                os.getcwd(): {
                    'bind': image.attrs['Config']['WorkingDir'],
                    'mode': 'rw',
                },
            },
        )
    return container


def end_container(container):
    container.stop()
    container.wait()
    container.remove(v=True)


@cli.command()
@click.pass_context
def stop(ctx):
    client = docker.from_env()
    project_name = ctx.obj["project_name"]
    for service, _ in ctx.obj['services'].items():
        name = f'{project_name}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            continue
        end_container(container)
    try:
        container = client.containers.get(f'{project_name}_tests')
    except docker.errors.NotFound:
        return
    end_container(container)


@cli.command()
@click.pass_context
def restart(ctx):  # pragma: no cover
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
@click.option('--dockerfile', '-f', type=click.Path(), default='Dockerfile', help='dockerfile to write too')
@click.pass_context
def render(ctx, template_file, dockerfile):
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
@click.option('--dockerfile', '-f', type=click.Path(), default='Dockerfile', help='dockerfile to write too')
@click.pass_context
def build(ctx, rebuild, tag, dockerfile):
    ctx.invoke(render, dockerfile=dockerfile)
    client = docker.from_env()

    if tag is None:
        tag = ctx.obj['tag']

    click.echo(f'Build Image: {tag}')

    for chunk in client.api.build(path='.', dockerfile=dockerfile, tag=tag, nocache=rebuild, rm=True):
        for line in chunk.split(b'\r\n'):
            if not line:
                continue
            data = json.loads(line)
            if 'stream' in data:
                click.echo(data['stream'], nl=False)

    return tag


@cli.command()
@click.pass_context
def exec(ctx):  # pragma: no cover
    container = ctx.invoke(start)
    os.execvp('docker', ['docker', 'exec', '-ti', container.id, 'bash'])


@cli.command()
@click.option('--step', '-s', help='Which step to run')
@click.argument('posargs', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(ctx, step, posargs):
    container = ctx.invoke(start)

    def run_command(command):
        command = command.format(
            posargs=' '.join(posargs),
        )
        click.echo(click.style(f'Run Command: {command}', fg='green'))
        socket = container.exec_run(
            cmd=command,
            tty=True,
            socket=True,
        )

        for line in socket.output:
            click.echo(line, nl=False)

    steps = ctx.obj['tests'].get('steps', {})
    if step:
        commands = [steps.get(step, '{posargs}')]
    else:
        commands = steps.values()
    for command in commands:
        if isinstance(command, list):
            for cmd in command:
                run_command(cmd)
        else:
            run_command(command)
