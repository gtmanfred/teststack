from teststack import cli


def test_env_with_containers(runner, testapp_dir):
    result = runner.invoke(cli, [f'--path={testapp_dir}', 'start', 'env', 'stop'])
    assert result.exit_code == 0
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME' in result.output
