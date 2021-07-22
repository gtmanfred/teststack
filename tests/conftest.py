import click.testing

import pytest

from teststack import import_commands


@pytest.fixture
def runner():
    import_commands()
    return click.testing.CliRunner()
