from teststack import cli


def test_running_tests_in_containers(runner, testapp_dir):

    result = runner.invoke(cli, [f'--path={testapp_dir}', 'stop', 'render', 'build', 'run', 'stop'])
    assert result.exit_code == 0
