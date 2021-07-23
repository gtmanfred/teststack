import click.testing

import pytest

from teststack import import_commands
from teststack.git import get_tag


@pytest.fixture
def runner():
    import_commands()
    return click.testing.CliRunner()


@pytest.fixture()
def tag():
    return get_tag()


@pytest.fixture()
def attrs():
    return {
        'NetworkSettings': {
            'IPAddress': 'fakeaddress',
            'Ports': {
                '5432/tcp': [
                    {'HostPort': '12345'},
                ],
                '5672/tcp': [
                    {'HostPort': '12537'},
                ],
                '12345/tcp': [],
            },
        },
    }
