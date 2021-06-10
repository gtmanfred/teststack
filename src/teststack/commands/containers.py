import click
import docker.errors

from teststack import cli


@cli.command()
@click.pass_context
def start(ctx):
    client = docker.from_env()
    for service, data in ctx.obj["config"].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            pass
        client.containers.run(
            image=data["image"],
            ports=data["ports"],
            detach=True,
            name=name,
            environment=data["environment"],
        )


@cli.command()
@click.pass_context
def stop(ctx):
    client = docker.from_env()
    for service, _ in ctx.obj["config"].items():
        name = f'{ctx.obj["project_name"]}_{service}'
        try:
            container = client.containers.get(name)
        except docker.errors.NotFound:
            return
        container.stop()
        container.remove()
