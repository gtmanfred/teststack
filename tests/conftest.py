import pathlib

import click.testing
import docker as docker_py

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


@pytest.fixture()
def docker():
    return docker_py.from_env()


@pytest.fixture(autouse=True)
def test_no_leftover_docker_containers(docker):
    yield
    assert not any(
        container.name.startswith('testapp') for container in docker.containers.list()
    ), '`testapp` containers were left behind, please clean them up in this test'
    assert not any(
        container.name.startswith('teststack') for container in docker.containers.list()
    ), '`teststack` containers were left behind, please clean them up in this test'
