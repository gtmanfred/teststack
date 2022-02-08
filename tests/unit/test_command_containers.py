import pathlib
import tempfile
from unittest import mock

from docker.errors import ImageNotFound
from docker.errors import NotFound

from teststack import cli


def test_render(runner, tag):
    with tempfile.NamedTemporaryFile() as tmpfile:
        result = runner.invoke(cli, ['render', f'--dockerfile={tmpfile.name}'])
        assert result.exit_code == 0
        with open(tmpfile.name, 'r') as fh_:
            assert fh_.readline() == 'FROM docker.io/python:slim\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert fh_.readline() == 'WORKDIR /srv\n'
            assert fh_.readline() == '\n'
            assert 'docker-metadata' in fh_.readline()
            assert tag['commit'] in fh_.readline()


def test_render_isolated(runner):
    with open('Dockerfile.j2') as fh_, runner.isolated_filesystem() as th_:

        with open('Dockerfile.j2', 'w') as wh_:
            wh_.write(fh_.read())

        result = runner.invoke(cli, [f'--path={th_}', 'render'])
        assert result.exit_code == 0
        with open('Dockerfile', 'r') as fh_:
            assert fh_.readline() == 'FROM docker.io/python:slim\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert fh_.readline() == 'WORKDIR /srv\n'
            assert not fh_.readline()


def test_container_start_no_tests(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start', '-n'])
    assert client.containers.get.call_count == 4
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
    assert client.containers.get.call_count == 11
    assert client.containers.run.called is False
    assert result.exit_code == 0


def test_container_start_with_tests_old_image(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 11
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
    assert client.containers.get.call_count == 6
    assert client.containers.run.call_count == 3
    assert result.exit_code == 0


def test_container_stop(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    with mock.patch('docker.from_env', return_value=client), mock.patch(
        'teststack.containers.docker.Client.end_container'
    ) as end_container:
        result = runner.invoke(cli, ['stop'])
    assert client.containers.get.call_count == 3
    assert end_container.call_count == 3
    assert result.exit_code == 0


def test_container_stop_without_containers(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    client.containers.get.side_effect = NotFound('container not found')
    with mock.patch('docker.from_env', return_value=client), mock.patch(
        'teststack.containers.docker.Client.end_container'
    ) as end_container:
        result = runner.invoke(cli, ['stop'])
    assert client.containers.get.call_count == 3
    assert end_container.called is False
    assert result.exit_code == 0


def test_container_build(runner, build_output):
    client = mock.MagicMock()
    client.api.build.return_value = build_output
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['build', '--tag=blah'])
    client.api.build.assert_called_with(path='.', dockerfile='Dockerfile', tag='blah', nocache=False, rm=True)
    assert result.exit_code == 0


def test_container_start_with_tests_without_image(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    image = mock.MagicMock()
    client.images.get.side_effect = [ImageNotFound('image not found'), image, image, image]
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 11
    assert client.containers.run.called is True
    assert client.images.get.call_count == 4
    assert result.exit_code == 0


def test_container_run(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    client.containers.get.return_value.exec_run.return_value.output = [
        'foo',
        'bar',
        'baz',
    ]
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['run'])
    assert client.containers.get.call_count == 14
    assert client.containers.run.called is False
    assert result.exit_code == 0
    assert 'foobarbaz' in result.output
    assert 'Run Command: env' in result.output


def test_container_run_step(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    client.containers.get.return_value.exec_run.return_value.output = [
        'foo',
        'bar',
        'baz',
    ]
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['run', '--step=install'])
    assert client.containers.get.call_count == 13
    assert client.containers.run.called is False
    assert result.exit_code == 0
    assert 'foobarbaz' in result.output
    assert 'Run Command: env' not in result.output
    assert 'Run Command: python -m pip install' in result.output
