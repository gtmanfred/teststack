import os
import subprocess
from unittest import mock

import pytest
from docker.errors import NotFound

from teststack import cli


def test_running_tests_in_containers(docker, runner, testapp_dir):

    result = runner.invoke(cli, [f'--path={testapp_dir}', 'stop', 'render', 'build', 'run'])
    assert result.exit_code == 0
    result = runner.invoke(cli, [f'--path={testapp_dir}', 'stop'])
    assert result.exit_code == 0


def test_running_tests(docker, runner, testapp_dir):

    result = runner.invoke(cli, [f'--path={testapp_dir}', 'stop', 'render', 'build', 'start', '-n'])
    assert result.exit_code == 0
    with pytest.raises(NotFound):
        docker.containers.get('testapp_tests')

    result = runner.invoke(cli, [f'--path={testapp_dir}', 'env', '-n'])
    assert result.exit_code == 0
    envvars = dict(map(lambda x: x.split('='), result.output.strip().split('\n')))
    envvars['PYTHONPATH'] = str(testapp_dir)
    with mock.patch.dict(os.environ, envvars):
        subprocess.run(['poetry', 'install'], cwd=testapp_dir)
        result = subprocess.run(['poetry', 'run', 'pytest'], cwd=testapp_dir)
        assert result.returncode == 0

    result = runner.invoke(cli, [f'--path={testapp_dir}', 'stop'])
    assert result.exit_code == 0
