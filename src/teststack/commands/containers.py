import json
import os.path
import pathlib

import click
import docker.errors
import jinja2

from teststack import cli


@cli.command()
@click.pass_context
def start(ctx):
    client = docker.from_env()
    for service, data in ctx.obj['services'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            container = None
        if container:
            continue
        client.containers.run(
            image=data['image'],
            ports=data['ports'],
            detach=True,
            name=name,
            environment=data['environment'],
        )


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
            return
        end_container(container)
    try:
        container = client.containers.get(f'{project_name}_tests')
    except docker.errors.NotFound:
        return
    end_container(container)


@cli.command()
@click.pass_context
def restart(ctx):
    ctx.invoke(stop)
    ctx.invoke(start)


@cli.command()
@click.option(
    '--template-file',
    '-t',
    type=click.Path(exists=True),
    default='Dockerfile.j2',
    help='template to render with jinja',
)
@click.option(
    '--docker-file', '-f', type=click.Path(exists=False), default='Dockerfile', help='dockerfile to write too'
)
def render(template_file, docker_file):
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

    template = env.get_template(template_file)
    template.stream(**os.environ).dump(docker_file)


@cli.command()
@click.option('--rebuild', '-r', is_flag=True, help='ignore cache and rebuild the container fully')
@click.option('--tag', '-t', default=None, help='Tag to label the build')
@click.pass_context
def build(ctx, rebuild, tag):
    ctx.invoke(render)
    client = docker.from_env()

    if tag is None:
        tag = ctx.obj['tag']

    click.echo(f'Build Image: {tag}')

    for chunk in client.api.build(path='.', tag=tag, nocache=rebuild, rm=True):
        for line in chunk.split(b'\r\n'):
            if not line:
                continue
            data = json.loads(line)
            if 'stream' in data:
                click.echo(data['stream'], nl=False)

    return tag


@cli.command()
@click.option('--step', '-s', help='Which step to run')
@click.argument('posargs', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(ctx, step, posargs):
    ctx.invoke(start)
    env = ctx.invoke(cli.get_command(ctx, 'env'), inside=True, no_export=True, quiet=True)

    client = docker.from_env()

    image = client.images.get(ctx.obj['tag'])
    name = f'{ctx.obj["project_name"]}_tests'
    try:
        container = client.containers.get(name)
    except docker.errors.NotFound:
        container = client.containers.run(
            image=image,
            stream=True,
            name=name,
            user=0,
            environment=env,
            command='tail -f /dev/null',
            detach=True,
            volumes={
                os.getcwd(): {
                    'bind': image.attrs['Config']['WorkingDir'],
                    'mode': 'rw',
                },
            },
        )
    steps = ctx.obj['config'].get('tests', {}).get('steps', {})
    if step:
        commands = [steps.get(step, '{posargs}')]
    else:
        commands = list(steps.values())
    for command in commands:
        click.echo(f'Run Command: {command}')
        command = command.format(
            posargs=' '.join(posargs),
        )
        socket = container.exec_run(
            cmd=command,
            tty=True,
            socket=True,
        )

        for line in socket.output:
            click.echo(line, nl=False)
