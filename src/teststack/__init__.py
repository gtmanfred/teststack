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
from .configuration import Configuration

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
    def __init__(self, *args, **kwargs):
        """
        The python builtin dictionary has 3 constructor signatures
        class dict(**kwargs)
        class dict(mapping, **kwargs)
        class dict(iterable, **kwargs)
        See https://docs.python.org/3/library/stdtypes.html#dict
        IMPORTANT:
        Note this takes any value in the dict suffixed with a '_' and strip that '_'
        This is in response to needing the field 'import' available, but that is a reserved
        python variable.
        """
        seq_or_mapping: typing.Mapping | typing.Iterable = args[0] if args else None
        if seq_or_mapping is not None:
            if hasattr(seq_or_mapping, "items"):
                # All Mapping types must have `items`
                arg: typing.Mapping = {self.field_name(k): v for k, v in seq_or_mapping.items() if v is not None}
            else:
                # If it's not a Mapping it must be an Iterable
                arg: typing.Iterable = ((self.field_name(k), v) for k, v in seq_or_mapping if v is not None)

            args = (arg, *args[1:])

        kwargs: typing.Mapping = {self.field_name(k): v for k, v in kwargs.items() if v is not None}

        super().__init__(*args, **kwargs)

    @staticmethod
    def field_name(key: str) -> str:
        """
        Takes any value in the dict prefixed with a '_' and strip that '_' This is in response to
        being unable to use reserved python keywords, such as "import", as field names in a dataclass
        """
        if key[0] == "_":
            key = key[1:]
        return key

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


def load_configuration(path: str, base_configuration: Configuration | None = None) -> Configuration:
    file = pathlib.Path(path)

    if not file.exists():
        raise FileNotFoundError(f"{path} does not exist")
    with file.open('r') as f:
        raw_config = toml.load(f)

    # Use the DictConfig class to handle the merge
    if base_configuration is not None:
        config_dictionary = asdict(base_configuration, dict_factory=DictConfig)
        new_config = DictConfig(raw_config)
        config_dictionary.merge(new_config)
    else:
        config_dictionary = DictConfig(raw_config)
    config = Configuration.load(config_dictionary)
    return config


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

    configuration: Configuration
    try:
        configuration = load_configuration(config)
    except FileNotFoundError:
        click.secho(f"Configuration file {config} not found; using defaults", fg='yellow', err=True)
        configuration = Configuration()

    try:
        configuration = load_configuration(local_config, base_configuration=configuration)
    except FileNotFoundError:
        pass
    config = asdict(configuration, dict_factory=DictConfig)

    if configuration.tests.min_version is not None:
        if Version(configuration.tests.min_version) > Version(__version__):
            click.echo(
                f'Current teststack version is too low, upgrade to at least {configuration.tests.min_version}',
                err=True,
            )
            sys.exit(10)

    ctx.obj['services'] = configuration.services
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
