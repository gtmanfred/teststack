import os.path
from distutils.version import LooseVersion

import click
import toml

from . import git
from .errors import IncompatibleVersionError

try:
    from importlib.metadata import entry_points
except ImportError:
    from backports.entry_points_selectable import entry_points

try:
    from ._version import version as __version__
except ImportError:  # pragma: no cover
    try:
        from setuptools_scm import get_version

        __version__ = get_version(root='..', relative_to=__file__)
    except ImportError:
        __version__ = None


@click.group(chain=True)
@click.option(
    '--config',
    '-c',
    type=click.Path(exists=True),
    default='teststack.toml',
    help='Location of teststack config.',
)
@click.option(
    '--project-name',
    '-n',
    default=None,
    help='Prefix for docker objects.',
)
@click.option('--path', '-p', default=os.getcwd(), type=click.Path(exists=True), help='Directory to run teststack in.')
@click.pass_context
def cli(ctx, config, project_name, path):
    ctx.ensure_object(dict)

    # change dir before everything else is calculated
    ctx.obj['currentdir'] = os.getcwd()
    os.chdir(path)

    with open(config, 'r') as fh_:
        config = toml.load(fh_)

    min_version = LooseVersion(config.get('tests', {}).get('min_version', 'v0.0.0').lstrip('v'))
    if min_version > LooseVersion(__version__):
        raise IncompatibleVersionError(f'Current teststack version is too low, upgrade to atleast {min_version}')

    ctx.obj['services'] = config.get('services', {})
    ctx.obj['tests'] = config.get('tests', {})
    ctx.obj['project_name'] = os.path.basename(path) if project_name is None else project_name
    ctx.obj.update(git.get_tag())


def import_commands():
    group = 'teststack.commands'
    entries = entry_points()

    if hasattr(entries, 'select'):
        entries = entries.select(group=group)
    else:
        entries = entries.get(group, [])

    for entry_point in entries:
        entry_point.load()


def main():  # pragma: no cover
    import_commands()
    cli()
