import pathlib
import tempfile
from unittest import mock

from docker.errors import NotFound

from teststack import cli


def test_render(runner, tag):
    with tempfile.NamedTemporaryFile() as tmpfile:
        result = runner.invoke(cli, ['render', f'--dockerfile={tmpfile.name}'])
        assert result.exit_code == 0
        with open(tmpfile.name, 'r') as fh_:
            assert fh_.readline() == 'FROM python:slim\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert fh_.readline() == '\n'
            assert 'docker-metadata' in fh_.readline()
            assert tag['commit'] in fh_.readline()


def test_render_isolated(runner, tag):
    with open('Dockerfile.j2') as fh_, runner.isolated_filesystem():

        pathlib.Path('teststack.toml').touch()
        with open('Dockerfile.j2', 'w') as wh_:
            wh_.write(fh_.read())

        result = runner.invoke(cli, ['render'])
        assert result.exit_code == 0
        with open('Dockerfile', 'r') as fh_:
            assert fh_.readline() == 'FROM python:slim\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert not fh_.readline()


def test_container_start_no_tests(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start', '-n'])
    assert client.containers.get.call_count == 2
    assert client.containers.run.called is False
    assert result.exit_code == 0


def test_container_start_no_tests_not_started(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    client.containers.get.side_effect = NotFound('container not found')
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start', '-n'])
    assert client.containers.get.call_count == 2
    assert client.containers.run.call_count == 2
    assert result.exit_code == 0


def test_container_start_with_tests(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 5
    assert client.containers.run.called is False
    assert result.exit_code == 0


def test_container_start_with_tests_old_image(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 5
    assert client.containers.run.called is True
    assert client.containers.get.return_value.stop.called is True
    assert client.containers.get.return_value.wait.called is True
    client.containers.get.return_value.remove.assert_called_with(v=True)
    assert result.exit_code == 0


def test_container_start_with_tests_not_started(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    client.containers.get.side_effect = NotFound('container not found')
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 5
    assert client.containers.run.call_count == 3
    assert result.exit_code == 0
