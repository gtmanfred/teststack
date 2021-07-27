import sys

import toml

import pytest

from teststack import cli
from teststack import import_commands
from teststack.errors import IncompatibleVersionError


def test_import_commands():
    import_commands()
    assert "teststack.commands.containers" in sys.modules
    assert "teststack.commands.environment" in sys.modules


def test_min_version(runner):
    with runner.isolated_filesystem() as th_:
        with open(f'{th_}/teststack.toml', 'w') as fh_:
            toml.dump({'tests': {'min_version': 'v999.999.999'}}, fh_)
        result = runner.invoke(cli, [f'--path={th_}', 'env'])
        assert result.exit_code == 10
