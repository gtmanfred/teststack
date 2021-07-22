from unittest import mock

from teststack import cli


def test_env_with_containers_inside(runner):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = {
        'NetworkSettings': {
            'IPAddress': 'fakeaddress',
            'Ports': {
                '5432/tcp': [
                    {'HostPort': '12345'},
                ],
                '5672/tcp': [
                    {'HostPort': '12537'},
                ],
                '12345/tcp': [
                    {'HostPort': '54321'},
                ],
            },
        },
    }
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['env', '--inside'])
    print(result.output)
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' in result.output
    assert 'POSTGRES_MAIN_HOST=fakeaddress' in result.output
    assert 'POSTGRES_MAIN_PORT=5432' in result.output


def test_env_with_containers_outside(runner):
    client = mock.MagicMock()
    client.containers.get.return_value.attrs = {
        'NetworkSettings': {
            'IPAddress': 'fakeaddress',
            'Ports': {
                '5432/tcp': [
                    {'HostPort': '12345'},
                ],
                '5672/tcp': [
                    {'HostPort': '12537'},
                ],
                '12345/tcp': [
                    {'HostPort': '54321'},
                ],
            },
        },
    }
    with mock.patch('docker.from_env', return_value=client):
        result = runner.invoke(cli, ['env'])
    print(result.output)
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME=bebop' in result.output
    assert 'POSTGRES_MAIN_HOST=localhost' in result.output
    assert 'POSTGRES_MAIN_PORT=12345' in result.output


def test_env_without_containers(runner):
    result = runner.invoke(cli, ['env'])
    assert 'AWS_ACCESS_KEY_ID' in result.output
