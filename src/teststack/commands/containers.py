import json
import os.path

import click
import jinja2

from teststack import cli


@cli.command()
@click.option('--no-tests', '-n', is_flag=True, help='Don\'t start the tests container')
@click.pass_context
def start(ctx, no_tests):
    client = ctx.obj['client']
    for service, data in ctx.obj['services'].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        container = client.container_get(name)
        if container is None:
            client.run(
                image=data['image'],
                ports=data.get('ports', {}),
                name=name,
                command=data.get('command', None),
                environment=data.get('environment', {}),
                mount_cwd=False,
            )

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
@click.pass_context
def build(ctx, rebuild, tag, dockerfile):
    ctx.invoke(render, dockerfile=dockerfile)
    client = ctx.obj['client']

    if tag is None:
        tag = ctx.obj['tag']

    click.echo(f'Build Image: {tag}')
    client.build(dockerfile, tag, rebuild)

    return tag


@cli.command()
@click.pass_context
def exec(ctx):  # pragma: no cover
    container = ctx.invoke(start)
    ctx.obj['client'].exec(container)


@cli.command()
@click.option('--step', '-s', help='Which step to run')
@click.argument('posargs', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(ctx, step, posargs):
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
