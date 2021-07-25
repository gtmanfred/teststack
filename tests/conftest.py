import pathlib

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


@pytest.fixture()
def build_output():
    chunks = []
    with open('tests/files/build.output', 'rb') as fh_:
        for line in fh_:
            line = line.replace(b'\\r\\n', b'\r\n')
            line = line.replace(b'\\\\', b'\\')
            chunks.append(line)
    return chunks


@pytest.fixture()
def main_dir():
    return pathlib.Path(__file__).parent.parent


@pytest.fixture()
def testapp_dir(main_dir):
    return main_dir / 'tests' / 'testapp'
