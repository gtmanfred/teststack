import os.path
import pathlib
import sys
from packaging.version import Version

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
        __version__ = 'v0.0.1'


class DictConfig(dict):
    def get(self, key, default=None):
        if isinstance(default, dict):
            default = DictConfig(default)
        rep = self
        for level in key.split('.'):
            if level not in rep:
                return default
            rep = rep[level]
        if isinstance(rep, dict):
            return DictConfig(rep)
        if isinstance(rep, str):
            try:
                return rep.format_map(os.environ)
            except KeyError:
                pass
        return rep

    def merge(self, config, inside=None):
        for key in config:
            if isinstance(self.get(key), dict):
                self.get(key).merge(config[key])
            self[key] = config[key]


@click.group(chain=True)
@click.option(
    '--config',
    '-c',
    type=click.Path(),
    default='teststack.toml',
    help='Location of teststack config.',
)
@click.option(
    '--local-config',
    '-l',
    type=click.Path(),
    default='teststack.local.toml',
    help='Local config to overwrite data in teststack.toml',
)
@click.option(
    '--project-name',
    '-n',
    default=None,
    help='Prefix for docker objects.',
)
@click.option('--path', '-p', default=os.getcwd(), type=click.Path(exists=True), help='Directory to run teststack in.')
@click.pass_context
def cli(ctx, config, local_config, project_name, path):
    ctx.ensure_object(DictConfig)
    config = pathlib.Path(config)
    local_config = pathlib.Path(local_config)

    @ctx.call_on_close
    def change_dir_to_original():
        os.chdir(ctx.obj['currentdir'])

    # change dir before everything else is calculated
    ctx.obj['currentdir'] = os.getcwd()
    os.chdir(path)

    if config.exists():
        with config.open('r') as fh_:
            config = DictConfig(toml.load(fh_))
    else:
        config = DictConfig()

    if local_config.exists():
        with local_config.open('r') as fh_:
            local_config = toml.load(fh_)
        config.merge(local_config)

    min_version = Version(config.get('tests.min_version', 'v0.0.0').lstrip('v'))
    if min_version > Version(__version__):
        click.echo(f'Current teststack version is too low, upgrade to atleast {min_version}', err=True)
        sys.exit(10)

    ctx.obj['services'] = config.get('services', {})
    ctx.obj['tests'] = config.get('tests', {})
    ctx.obj['project_name'] = os.path.basename(path.strip('/')) if project_name is None else project_name

    ctx.obj['client'] = get_client(config.get('client', {}))
    ctx.obj['prefix'] = config.get('client.prefix', '')
    ctx.obj.update(git.get_tag(prefix=config.get('client.prefix', '')))


def get_client(client):
    group = 'teststack.clients'
    entries = entry_points()

    if hasattr(entries, 'select'):
        entries = entries.select(group=group)
    else:
        entries = entries.get(group, [])

    client_name = client.pop('name', 'docker')
    for entry_point in entries:
        if entry_point.name == client_name:
            return entry_point.load().Client(**client)


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
