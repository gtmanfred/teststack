from unittest import mock
import traceback
from docker.errors import NotFound

from teststack import cli


def test_env_with_containers_inside(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs

    result = runner.invoke(cli, ['env', '--inside'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' in result.output
    assert 'POSTGRES_MAIN_HOST=fakeaddress' in result.output
    assert 'POSTGRES_MAIN_PORT=5432' in result.output


def test_env_with_containers_outside(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs

    result = runner.invoke(cli, ['env'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' in result.output
    assert 'POSTGRES_MAIN_HOST=localhost' in result.output
    assert 'POSTGRES_MAIN_PORT=12345' in result.output


def test_env_with_containers_no_export(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs

    result = runner.invoke(cli, ['env', '--no-export'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert 'export' not in result.output


def test_env_without_containers(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs
    client.containers.get.side_effect = NotFound('container not found')

    result = runner.invoke(cli, ['env'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' not in result.output
    assert 'POSTGRES_MAIN_HOST=localhost' not in result.output
    assert 'POSTGRES_MAIN_PORT=12345' not in result.output


def test_env_without_containers_quiet(runner, client):
    client.containers.get.side_effect = NotFound('container not found')

    result = runner.invoke(cli, ['env', '--quiet'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert 'AWS_ACCESS_KEY_ID' not in result.output


def test_env_empty(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['--path=.', 'import-env'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert not result.output.strip()
