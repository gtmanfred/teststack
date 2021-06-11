import os.path
import pathlib

try:
    from importlib import metadata
except ImportError:
    metadata = None
    import pkg_resources

import click
import git

from teststack.config import get_config

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
    type=pathlib.Path,
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
    ctx.obj['config'] = get_config(config)
    ctx.obj['project_name'] = project_name

    repo = git.Repo('.')
    name = pathlib.Path(repo.remote('origin').url)
    tag = ':'.join(
        [
            name.with_suffix('').name,
            repo.head.commit.hexsha,
        ]
    )
    ctx.obj['tag'] = tag


def import_commands():
    group = 'teststack.commands'
    for entry_point in metadata.entry_points().get(group, []) if metadata else pkg_resources.iter_entry_points(group):
        entry_point.load()


def main():
    import_commands()
    cli()
