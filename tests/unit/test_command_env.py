from unittest import mock

from docker.errors import NotFound

from teststack import cli


def test_env_with_containers_inside(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['env', '--inside'])
    assert result.exit_code == 0
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' in result.output
    assert 'POSTGRES_MAIN_HOST=fakeaddress' in result.output
    assert 'POSTGRES_MAIN_PORT=5432' in result.output


def test_env_with_containers_outside(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['env'])
    assert result.exit_code == 0
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' in result.output
    assert 'POSTGRES_MAIN_HOST=localhost' in result.output
    assert 'POSTGRES_MAIN_PORT=12345' in result.output


def test_env_without_containers(runner, attrs):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = attrs
    client.containers.get.side_effect = NotFound('container not found')
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['env'])
    assert result.exit_code == 0
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' not in result.output
    assert 'POSTGRES_MAIN_HOST=localhost' not in result.output
    assert 'POSTGRES_MAIN_PORT=12345' not in result.output


def test_env_without_containers_quiet(runner):
    client = mock.MagicMock()
    client.containers.get.side_effect = NotFound('container not found')
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['env', '--quiet'])
    assert result.exit_code == 0
    assert 'AWS_ACCESS_KEY_ID' not in result.output
