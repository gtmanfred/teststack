from teststack.git import get_tag
from teststack.git import get_path

from unittest.mock import patch


def test_get_tag_isolated(runner, tag):
    with runner.isolated_filesystem():
        tag = get_tag()['tag']
        assert tag.endswith(':latest')


def test_get_tag_isolated_prefix(runner, tag):
    with runner.isolated_filesystem():
        tag = get_tag(prefix='hub.docker.com/')['tag']
        assert tag.endswith(':latest')
        assert tag.startswith('hub.docker.com/')


def test_get_tag_isolated_prefix_without_slash(runner, tag):
    with runner.isolated_filesystem():
        tag = get_tag(prefix='hub.docker.com')['tag']
        assert tag.endswith(':latest')
        assert tag.startswith('hub.docker.com/')


def test_get_repo(runner):
    with runner.isolated_filesystem(), patch('git.Repo') as mock_repo:
        path = get_path('https://github.com/gtmanfred/teststack')
    assert str(path) == '.teststack/repos/gtmanfred/teststack'
    assert mock_repo.clone_from.called


def test_get_repo_with_ref(runner):
    with runner.isolated_filesystem(), patch('git.Repo') as mock_repo:
        get_path('https://github.com/gtmanfred/teststack', ref='blah')
    mock_repo.clone_from.return_value.checkout.assert_called_once_with('blah')


def test_get_repo_path_exists(runner):
    with runner.isolated_filesystem(), patch('git.Repo') as mock_repo, patch('pathlib.Path') as mock_path:
        mock_path.return_value.exists.return_value = True
        get_path('https://github.com/gtmanfred/teststack')
    assert mock_repo.clone_from.called is False


def test_get_repo_path():
    with patch('git.Repo') as mock_repo:
        path = get_path('tests/testapp')
    assert mock_repo.clone_from.called is False
    assert str(path) == 'tests/testapp'
