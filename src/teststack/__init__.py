import typing
import os.path
import pathlib
import sys
from packaging.version import Version
from dataclasses import asdict

import click
import toml

from . import git
from .errors import IncompatibleVersionError
from .configuration import Configuration, ClientConfiguration

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


def load_configuration(path: str, base_configuration: DictConfig | None = None) -> DictConfig:
    file = pathlib.Path(path)

    if not file.exists():
        raise FileNotFoundError(f"{path} does not exist")
    with file.open('r') as f:
        raw_configuration = toml.load(f)

    # Use the DictConfig class to handle the merge
    configuration = DictConfig(raw_configuration)
    if base_configuration is not None:
        base_configuration.merge(configuration)
        return base_configuration
    else:
        return configuration


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

    @ctx.call_on_close
    def change_dir_to_original():
        os.chdir(ctx.obj['currentdir'])

    # change dir before everything else is calculated
    ctx.obj['currentdir'] = os.getcwd()
    os.chdir(path)

    try:
        config = load_configuration(config)
    except FileNotFoundError:
        click.secho(f"Configuration file {config} not found; using defaults", fg='yellow', err=True)
        config = DictConfig()

    try:
        config = load_configuration(local_config, base_configuration=config)
    except FileNotFoundError:
        pass
    configuration: Configuration = Configuration.load(config)

    if configuration.tests.min_version is not None:
        if Version(configuration.tests.min_version) > Version(__version__):
            click.echo(
                f'Current teststack version is too low, upgrade to at least {configuration.tests.min_version}',
                err=True,
            )
            sys.exit(10)

    ctx.obj['services'] = configuration.services
    ctx.obj['tests'] = configuration.tests
    ctx.obj['project_name'] = os.path.basename(path.strip('/')) if project_name is None else project_name

    ctx.obj['client'] = get_client(configuration.client)
    ctx.obj['prefix'] = configuration.client.prefix
    ctx.obj.update(git.get_tag(prefix=configuration.client.prefix))


def get_client(client: ClientConfiguration):
    group = 'teststack.clients'
    entries = entry_points()

    if hasattr(entries, 'select'):
        entries = entries.select(group=group)
    else:
        entries = entries.get(group, [])

    client_name = client.name
    for entry_point in entries:
        if entry_point.name == client_name:
            return entry_point.load().Client(**client.kwargs)


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
