import json
import pathlib
from unittest.mock import patch

import click.testing
import docker as docker_py

import pytest

from teststack import import_commands
from teststack.containers.docker import Client
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
            'Ports': {
                '5432/tcp': [
                    {'HostPort': '12345'},
                ],
                '5672/tcp': [
                    {'HostPort': '12537'},
                ],
                '6379/tcp': [
                    {'HostPort': '19999'},
                ],
                '12345/tcp': [],
            },
            'Networks': {
                'teststack': {
                    'IPAddress': 'fakeaddress',
                },
            },
        },
    }


@pytest.fixture()
def build_output():
    chunks = []
    with open('tests/files/build.output', 'rb') as fh_:
        for chunk in fh_:
            chunk = chunk.replace(b'\\r\\n', b'\r\n')
            chunk = chunk.replace(b'\\\\', b'\\')
            for line in chunk.split(b'\r\n'):
                if not line:
                    continue
                chunks.append(json.loads(line))
    return chunks


@pytest.fixture()
def main_dir():
    return pathlib.Path(__file__).parent.parent


@pytest.fixture()
def testapp_dir(main_dir):
    return main_dir / 'tests' / 'testapp'


@pytest.fixture()
def test_files_dir(main_dir):
    return main_dir / 'tests' / 'files'


@pytest.fixture()
def client():
    context = docker_py.ContextAPI.get_current_context()
    if context.name == 'default':  # pragma: no branch
        with patch('docker.from_env') as client:
            yield client.return_value
    else:
        with patch('docker.DockerClient') as client:
            yield client.return_value


@pytest.fixture()
def docker():
    return Client().client


@pytest.fixture(autouse=True)
def test_no_leftover_docker_containers(docker):
    yield
    assert not any(
        container.name.startswith('testapp') for container in docker.containers.list()
    ), '`testapp` containers were left behind, please clean them up in this test'
    assert not any(
        container.name.startswith('teststack') for container in docker.containers.list()
    ), '`teststack` containers were left behind, please clean them up in this test'
