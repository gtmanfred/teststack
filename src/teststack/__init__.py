import os.path
import pathlib

import click
import git.exc
import toml

try:
    from importlib.metadata import entry_points
except ImportError:
    from backports.entry_points_selectable import entry_points

try:
    from ._version import version as __version__
except ImportError:
    try:
        from setuptools_scm import get_version

        __version__ = get_version(root='..', relative_to=__file__)
    except ImportError:
        __version__ = None


@click.group(chain=True)
@click.option(
    '--config',
    '-c',
    type=click.File(),
    default='teststack.toml',
    help='Location of teststack config.',
)
@click.option(
    '--project-name',
    '-p',
    default=os.path.basename(os.getcwd()),
    help='Prefix for docker objects.',
)
@click.pass_context
def cli(ctx, config, project_name):
    ctx.ensure_object(dict)
    config = toml.load(config)
    ctx.obj['services'] = config.get('services', {})
    ctx.obj['tests'] = config.get('tests', {})
    ctx.obj['project_name'] = project_name

    try:
        repo = git.Repo('.')
        name = pathlib.Path(repo.remote('origin').url)
        tag = ':'.join(
            [
                name.with_suffix('').name,
                repo.head.commit.hexsha,
            ]
        )
        ctx.obj['tag'] = tag
        ctx.obj['commit'] = repo.head.commit.hexsha
    except git.exc.InvalidGitRepositoryError:
        ctx.obj['tag'] = ':'.join(
            [
                os.path.basename(os.getcwd()),
                'latest',
            ]
        )


def import_commands():
    group = 'teststack.commands'
    entries = entry_points()

    if hasattr(entries, 'select'):
        entries = entries.select(group=group)
    else:
        entries = entries.get(group, [])

    for entry_point in entries:
        entry_point.load()


def main():
    import_commands()
    cli()
