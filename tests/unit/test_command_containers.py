import os
import tempfile
from unittest import mock
from xml.etree.ElementTree import ElementTree

from docker.errors import ImageNotFound
from docker.errors import NotFound
from teststack import cli
from teststack.commands import containers
from teststack.commands.containers import Command


# TODO: Fix these.
#  What exactly each case tests is unclear because the mocks are near gibberish (at least to me)
#  Plus the mocks appear to assume implementation details which is bad practice


def test_render(runner, tag):
    with tempfile.NamedTemporaryFile() as tmpfile:
        result = runner.invoke(cli, ['render', f'--dockerfile={tmpfile.name}'], catch_exceptions=False)
        assert result.exit_code == 0
        with open(tmpfile.name) as fh_:
            assert fh_.readline() == 'FROM docker.io/python:3.9\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert fh_.readline() == 'WORKDIR /srv\n'
            assert fh_.readline() == '\n'
            assert tag['commit'] in fh_.readline()


def test_render_with_env_var_override(runner):
    with tempfile.NamedTemporaryFile() as tmpfile:
        with mock.patch.dict(os.environ, {'GIT_BRANCH': 'other'}):
            result = runner.invoke(cli, ['render', f'--dockerfile={tmpfile.name}'], catch_exceptions=False)
            assert result.exit_code == 0


def test_render_isolated(runner):
    with open('Dockerfile.j2') as fh_, runner.isolated_filesystem() as th_:
        with open('Dockerfile.j2', 'w') as wh_:
            wh_.write(fh_.read())

        result = runner.invoke(cli, [f'--path={th_}', 'render'], catch_exceptions=False)
        assert result.exit_code == 0
        with open('Dockerfile') as fh_:
            assert fh_.readline() == 'FROM docker.io/python:3.9\n'
            assert fh_.readline() == 'ENV PYTHON=True\n'
            assert fh_.readline() == 'WORKDIR /srv\n'
            assert not fh_.readline()


def test_container_start_no_tests(runner, attrs, client):
    # Invoking 'start' with the --no-tests/-n parameter should not run or reference the test container
    client.containers.get.return_value.attrs = attrs
    client.containers.get.return_value.status = "running"

    test_app_test_image_name = "teststack.testapp_tests"  # Imported tests
    test_image_name = "teststack_tests"  # Always set to {prefix}{project_name}_tests

    result = runner.invoke(cli, ['start', '-n'], catch_exceptions=False)
    print(result.stdout, result.stderr)
    assert result.exit_code == 0

    # Test image was not run
    for call in client.containers.run.call_args_list:
        assert call.kwargs["name"] != test_image_name, "Main test container was run"
        assert call.kwargs["name"] != test_app_test_image_name, "Imported test container was run"
    # Test container was not queried
    for call in client.containers.get.call_args_list:
        assert call.args[0] != test_image_name, "Main test container was queried"
        assert call.args[0] != test_app_test_image_name, "Imported test container was queried"


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
    ] + [container] * 22

    result = runner.invoke(cli, ['start', '-n'], catch_exceptions=False)
    # assert client.containers.get.call_count == 16
    # assert client.containers.run.call_count == 2
    assert result.exit_code == 0


def test_container_start_with_tests(runner, attrs, client):
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    client.containers.get.return_value.attrs = attrs
    client.containers.get.return_value.status = "running"

    result = runner.invoke(cli, ['start'], catch_exceptions=False)
    assert client.containers.get.called is True
    # assert client.containers.get.call_count == 30
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
    ] + [container] * 48

    result = runner.invoke(cli, ['start'], catch_exceptions=False)
    assert client.containers.get.called is True
    # assert client.containers.get.call_count == 29

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

    result = runner.invoke(cli, ['start'], catch_exceptions=False)
    # assert client.containers.get.call_count == 29
    # assert client.containers.run.call_count == 3

    assert result.exit_code == 0


def test_container_stop(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs

    with mock.patch('teststack.containers.docker.Client.end_container') as end_container:
        result = runner.invoke(cli, ['stop'], catch_exceptions=False)
    assert client.containers.get.call_count == 7
    assert end_container.call_count == 7
    assert result.exit_code == 0


def test_container_stop_without_containers(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs
    client.containers.get.side_effect = NotFound('container not found')

    with mock.patch('teststack.containers.docker.Client.end_container') as end_container:
        result = runner.invoke(cli, ['stop'], catch_exceptions=False)
    assert client.containers.get.call_count == 7
    assert end_container.called is False
    assert result.exit_code == 0


def test_container_build(runner, client, build_command):
    result = runner.invoke(cli, ['build', '--tag=blah'], catch_exceptions=False)
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
    result = runner.invoke(cli, ['build', '--service=cache'], catch_exceptions=False)
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
    result = runner.invoke(cli, ['build', '--service=cache', '--tag=blah'], catch_exceptions=False)
    assert result.exit_code == 0
    build_command.assert_called_with(
        [
            "docker",
            "build",
            "--file=tests/redis/Dockerfile",
            "--tag=blah",
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
    ] + [container] * 48
    image = mock.MagicMock()
    client.images.get.side_effect = [image, ImageNotFound('image not found'), image, image, image]

    result = runner.invoke(cli, ['start'], catch_exceptions=True)
    print(result.stdout)
    assert client.containers.get.called is True
    # assert client.containers.get.call_count == 29

    assert client.containers.run.called is True
    # assert client.images.get.call_count == 5
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

    result = runner.invoke(cli, ['run'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert client.containers.get.called is True
    # assert client.containers.get.call_count == 33

    assert client.containers.run.called is False
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

    result = runner.invoke(cli, ['run', '--step=install'], catch_exceptions=False)
    assert result.exit_code == 0, f"Result: {result.output}"
    assert client.containers.get.called is True
    # assert client.containers.get.call_count == 31

    assert client.containers.run.called is False
    assert 'foobarbaz' in result.output
    assert 'Run Command: test -f /etc/hosts1323' not in result.output
    assert 'Run Command: env' not in result.output
    assert 'Run Command: python -m pip install' in result.output


def test_container_run_step_invalid_step(runner, attrs, client):
    client.containers.get.return_value.attrs = attrs
    client.images.get.return_value.id = client.containers.get.return_value.image.id
    client.containers.get.return_value.client.api.exec_start.return_value = [
        'foo',
        'bar',
        'baz',
    ]
    client.containers.get.return_value.client.api.exec_inspect.return_value = {
        'ExitCode': 0,
    }

    result = runner.invoke(cli, ['run', '--step=stepthatdoesnotexist'])
    assert result.exit_code != 0
    assert client.containers.run.called is False
    print(result.stdout)
    print(result.stderr)
    print(result.exit_code)
    assert 'stepthatdoesnotexist is not an available step' in result.stderr


def test_container_tag(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['tag'], catch_exceptions=False)
    assert result.stdout.startswith('teststack:')


def test_container_status_notfound(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['status'], catch_exceptions=False)
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

    result = runner.invoke(cli, ['copy'], catch_exceptions=False)
    assert result.exit_code == 0
    assert os.path.exists('garbage.xml')
    et = ElementTree()
    et.parse(source='garbage.xml')
    assert et.find('testsuite')


def test_do_check(client):
    # Test checks are not re-run and exit code is correctly set
    command = Command(name="test", command=["ls"], check="grep")
    with mock.patch.object(containers, "_run") as run:
        run.return_value = 100
        # First time should run the check
        exit_code = containers._do_check(command, {})
        assert run.called
        assert exit_code == 100
        assert command.check_exit_code == 100
        # Second time should not
        run.reset_mock()
        exit_code = containers._do_check(command, {})
        assert not run.called
        assert exit_code == 100
        assert command.check_exit_code == 100


def test_container_command_check_exit_code_requires(client):
    commands = {
        "test": Command(name="test", command=["pytest"], required_by={"report"}),
        "report": Command(name="report", check="test -f junit.xml", command=["coverage"], requires=["test"]),
    }
    with mock.patch.object(containers, "_run") as run:
        run.return_value = 0
        # Check on report should be run (for some reason???)
        containers._do_check(commands["test"], {"commands": commands})
        assert run.called
        assert commands["report"].check_exit_code == 0


def test_container_command__run_command_required_by_already_run(client):
    # Command should exit with exit code 0 if a command that requires it already failed?
    commands = {
        "pre-test": Command(name="pre-test", command=["touch test-file"], required_by={"test"}),
        "test": Command(name="test", command=["pytest"], requires=["pre-test"], exit_code=128),
    }
    assert containers._run_command(commands["pre-test"], {"commands": commands}) == 0


# def test_container_command__run_command_required_by(client):
#     exit_code = 128
#     client.run_command.return_value.__radd__.return_value = exit_code
#     assert (
#         containers._run_command(
#             command={'required_by': ['blah'], 'command': 'whatever', 'user': None},
#             ctx={
#                 'client': client,
#                 'container': 'whatever',
#                 'posargs': '',
#                 'commands': {
#                     'blah': {},
#                 },
#             },
#         )
#         == exit_code
#     )
