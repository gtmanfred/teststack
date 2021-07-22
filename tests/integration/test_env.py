from teststack import cli


def test_env_with_containers(runner):
    result = runner.invoke(cli, ['start', 'env', 'stop'])
    assert 'AWS_ACCESS_KEY_ID' in result.output
    assert 'POSTGRES_MAIN_DBNAME' in result.output
