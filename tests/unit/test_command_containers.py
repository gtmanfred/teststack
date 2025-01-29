import os
import tempfile
from unittest import mock
from xml.etree.ElementTree import ElementTree

from docker.errors import ImageNotFound
from docker.errors import NotFound
from teststack import cli
from teststack.commands import containers


def test_render(runner, tag):
    with tempfile.NamedTemporaryFile() as tmpfile:
        result = runner.invoke(cli, ['render', f'--dockerfile={tmpfile.name}'])
        assert result.exit_code == 0
        with open(tmpfile.name) as fh_:
            assert fh_.readline() == 'FROM docker.io/python:3.9\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert fh_.readline() == 'WORKDIR /srv\n'
            assert fh_.readline() == '\n'
            assert 'docker-metadata' in fh_.readline()
            assert tag['commit'] in fh_.readline()


def test_render_with_env_var_override(runner):
    with tempfile.NamedTemporaryFile() as tmpfile:
        with mock.patch.dict(os.environ, {'GIT_BRANCH': 'other'}):
            result = runner.invoke(cli, ['render', f'--dockerfile={tmpfile.name}'])
            assert result.exit_code == 0


def test_render_isolated(runner):
    with open('Dockerfile.j2') as fh_, runner.isolated_filesystem() as th_:
        with open('Dockerfile.j2', 'w') as wh_:
            wh_.write(fh_.read())

        result = runner.invoke(cli, [f'--path={th_}', 'render'])
        assert result.exit_code == 0
        with open('Dockerfile') as fh_:
            assert fh_.readline() == 'FROM docker.io/python:3.9\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert fh_.readline() == 'WORKDIR /srv\n'
            assert not fh_.readline()


def test_container_start_no_tests(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs
    client.containers.get.return_value.status = "running"

    result = runner.invoke(cli, ['start', '-n'])
    assert client.containers.get.call_count == 17
    assert client.containers.run.called is False
    assert result.exit_code == 0


def test_container_start_no_tests_not_started(runner, attrs, client):
    container = mock.MagicMock()
    container.status = "running"
    container.attrs = attrs
    client.containers.get.side_effect = [
        NotFound('container not found'),
        container,
        NotFound('container not found'),
        container,
        NotFound('container not found'),
    ] + [container] * 11

    result = runner.invoke(cli, ['start', '-n'])
    assert client.containers.get.call_count == 16
    assert client.containers.run.call_count == 2
    assert result.exit_code == 0


def test_container_start_with_tests(runner, attrs, client):
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    client.containers.get.return_value.attrs = attrs
    client.containers.get.return_value.status = "running"

    result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 30
    assert client.containers.run.called is False
    assert result.exit_code == 0


def test_container_start_with_tests_old_image(runner, attrs, client):
    container = mock.MagicMock()
    container.attrs = attrs
    container.status = "running"
    client.containers.get.side_effect = [
        NotFound('container not found'),
        container,
        NotFound('container not found'),
        container,
        NotFound('container not found'),
    ] + [container] * 24

    result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 29
    assert client.containers.run.called is True
    assert container.stop.called is True
    assert container.wait.called is True
    container.remove.assert_called_with(v=True)
    assert result.exit_code == 0


def test_container_start_with_tests_not_started(runner, attrs, client):
    container = mock.MagicMock()
    container.attrs = attrs
    container.status = "running"
    client.containers.get.side_effect = [
        NotFound('container not found'),
        container,
        NotFound('container not found'),
        container,
        NotFound('container not found'),
    ] + [container] * 30

    result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 29
    assert client.containers.run.call_count == 3
    assert result.exit_code == 0


def test_container_stop(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs

    with mock.patch('teststack.containers.docker.Client.end_container') as end_container:
        result = runner.invoke(cli, ['stop'])
    assert client.containers.get.call_count == 7
    assert end_container.call_count == 7
    assert result.exit_code == 0


def test_container_stop_without_containers(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs
    client.containers.get.side_effect = NotFound('container not found')

    with mock.patch('teststack.containers.docker.Client.end_container') as end_container:
        result = runner.invoke(cli, ['stop'])
    assert client.containers.get.call_count == 7
    assert end_container.called is False
    assert result.exit_code == 0


def test_container_build(runner, client, build_command):
    result = runner.invoke(cli, ['build', '--tag=blah'])
    assert result.exit_code == 0
    build_command.assert_called_with(
        [
            "docker",
            "build",
            "--file=./Dockerfile",
            "--tag=blah",
            "--rm",
            ".",
            f"--secret=id=netrc,source={os.path.expanduser('~/.netrc')}",
        ]
    )


def test_container_build_service(runner, client, tag, build_command):
    result = runner.invoke(cli, ['build', '--service=cache'])
    assert result.exit_code == 0
    build_command.assert_called_with(
        [
            "docker",
            "build",
            "--file=tests/redis/Dockerfile",
            f"--tag=cache:{tag['commit']}",
            "--rm",
            "tests/redis",
            "--build-arg=REDIS_VERSION=latest",
        ]
    )


def test_container_build_service_with_tag(runner, build_command, client):
    result = runner.invoke(cli, ['build', '--service=cache', '--tag=blah'])
    assert result.exit_code == 0
    build_command.assert_called_with(
        [
            "docker",
            "build",
            "--file=tests/redis/Dockerfile",
            f"--tag=blah",
            "--rm",
            "tests/redis",
            "--build-arg=REDIS_VERSION=latest",
        ]
    )


def test_container_start_with_tests_without_image(runner, attrs, client):
    container = mock.MagicMock()
    container.status = "running"
    container.attrs = attrs
    client.containers.get.side_effect = [
        NotFound('container not found'),
        container,
        NotFound('container not found'),
        container,
        NotFound('container not found'),
    ] + [container] * 24
    image = mock.MagicMock()
    client.images.get.side_effect = [image, ImageNotFound('image not found'), image, image, image]

    result = runner.invoke(cli, ['start'])
    assert client.containers.get.call_count == 29
    assert client.containers.run.called is True
    assert client.images.get.call_count == 5
    assert result.exit_code == 0


def test_container_run(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs
    client.containers.get.return_value.status = "running"
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    client.containers.get.return_value.client.api.exec_start.return_value = [
        'foo',
        'bar',
        'baz',
    ]
    client.containers.get.return_value.client.api.exec_inspect.return_value = {
        'ExitCode': 0,
    }

    result = runner.invoke(cli, ['run'])
    assert client.containers.get.call_count == 33
    assert client.containers.run.called is False
    assert result.exit_code == 0
    assert 'foobarbaz' in result.output
    assert 'Run Command: test -f /etc/hosts1323' in result.output
    assert 'Run Command: env' not in result.output


def test_container_run_step(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs
    client.containers.get.return_value.status = "running"
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    client.containers.get.return_value.client.api.exec_start.return_value = [
        'foo',
        'bar',
        'baz',
    ]

    client.containers.get.return_value.client.api.exec_inspect.return_value = {
        'ExitCode': 0,
    }

    result = runner.invoke(cli, ['run', '--step=install'])
    assert client.containers.get.call_count == 31
    assert client.containers.run.called is False
    assert result.exit_code == 0
    assert 'foobarbaz' in result.output
    assert 'Run Command: test -f /etc/hosts1323' not in result.output
    assert 'Run Command: env' not in result.output
    assert 'Run Command: python -m pip install' in result.output


def test_container_tag(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['tag'])
    assert result.stdout.startswith('teststack:')


def test_container_status_notfound(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['status'])
    assert 'notfound' in result.stdout


def test_container_copy_raises(runner, client):
    client.containers.get.return_value.get_archive.side_effect = NotFound(message='notfound')
    client.containers.get.return_value.attrs = {'Config': {'WorkingDir': '/srv'}}

    result = runner.invoke(cli, ['copy'])
    assert result.exit_code == 12


def test_container_copy(runner, client, test_files_dir):
    archive = test_files_dir / 'testapp.tar'
    with archive.open('rb') as fh_:
        data = fh_.read()
    client.containers.get.return_value.get_archive.return_value = ([data], {})
    client.containers.get.return_value.attrs = {'Config': {'WorkingDir': '/srv'}}

    result = runner.invoke(cli, ['copy'])
    assert result.exit_code == 0
    assert os.path.exists('garbage.xml')
    et = ElementTree()
    et.parse(source='garbage.xml')
    assert et.find('testsuite')


def test_container_command_check_exit_code(client):
    exit_code = 100
    assert containers._do_check({'check_exit_code': exit_code}, None) == exit_code


def test_container_command_check_exit_code_requires(client):
    exit_code = 0
    assert (
        containers._do_check(
            {'required_by': ['blah']},
            {
                'commands': {
                    'blah': {'check_exit_code': exit_code},
                }
            },
        )
        == 0
    )


def test_container_command__run_command_required_by_already_run(client):
    exit_code = 128
    assert (
        containers._run_command(
            command={'required_by': ['blah']},
            ctx={
                'commands': {
                    'blah': {
                        'exit_code': exit_code,
                    },
                },
            },
        )
        == 0
    )


def test_container_command__run_command_required_by(client):
    exit_code = 128
    client.run_command.return_value.__radd__.return_value = exit_code
    assert (
        containers._run_command(
            command={'required_by': ['blah'], 'command': 'whatever', 'user': None},
            ctx={
                'client': client,
                'container': 'whatever',
                'posargs': '',
                'commands': {
                    'blah': {},
                },
            },
        )
        == exit_code
    )
