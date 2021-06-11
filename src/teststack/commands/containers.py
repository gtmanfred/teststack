import json
import os.path
import pathlib

import click
import docker.errors
import git
import jinja2

from teststack import cli


@cli.command()
@click.pass_context
def start(ctx):
    client = docker.from_env()
    for service, data in ctx.obj['config'].items():
        if service.startswith('service'):
            continue
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


@cli.command()
@click.pass_context
def stop(ctx):
    client = docker.from_env()
    for service, _ in ctx.obj['config'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            return
        container.stop()
        container.remove()


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
@click.option('--quiet', '-q', is_flag=True, help='Do not print out information')
@click.pass_context
def build(ctx, rebuild, tag, quiet):
    ctx.invoke(render)
    client = docker.from_env()

    if tag is None:
        repo = git.Repo('.')
        name = pathlib.Path(repo.remote('origin').url)
        tag = ':'.join(
            [
                name.with_suffix('').name,
                repo.head.commit.hexsha,
            ]
        )

    if ctx.obj.get('build', False) is True:
        return tag

    click.echo(f'Build Image: {tag}')

    for chunk in client.api.build(path='.', tag=tag, nocache=rebuild, rm=True):
        for line in chunk.split(b'\r\n'):
            if not line:
                continue
            data = json.loads(line)
            if 'stream' in data:
                click.echo(data['stream'], nl=False)

    if quiet is False:
        click.echo(f'Image Built: {tag}')
    ctx.obj['build'] = True

    return tag


@cli.command()
@click.pass_context
def run(ctx):
    image = ctx.invoke(build, quiet=True)
    ctx.invoke(start)
    env = ctx.invoke(cli.get_command(ctx, 'env'), inside=True, no_export=True, quiet=True)

    client = docker.from_env()

    image = client.images.get(image)
    container = client.containers.run(
        image=image,
        stream=True,
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

    for command in ctx.obj['config'].get('service', {}).get('commands', []):
        click.echo(f'Run Command: {command}')
        socket = container.exec_run(
            cmd=command,
            tty=True,
            socket=True,
        )

        for line in socket.output:
            click.echo(line, nl=False)

    container.stop()
    container.wait()
    container.remove(v=True)
