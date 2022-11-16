import os
import pathlib
import urllib.parse

import git.exc


def get_path(repo, ref=None):
    if os.path.exists(repo):
        path = repo
    else:
        urlobj = urllib.parse.urlparse(repo)
        path = pathlib.Path(f'.teststack/repos{urlobj.path}')
        if path.exists():
            repo = git.Repo(str(path))
        else:
            path.mkdir(exist_ok=True, parents=True)
            repo = git.Repo.clone_from(repo, str(path))
        if ref:
            repo.checkout(ref)

    return path


def get_tag(prefix=''):
    if prefix and not prefix.endswith('/'):
        prefix = f'{prefix}/'
    try:
        repo = git.Repo('.')
        name = pathlib.Path(repo.remote('origin').url)
        tag = ':'.join(
            [
                name.with_suffix('').name,
                repo.head.commit.hexsha,
            ]
        )
        tag = f'{prefix}{tag}'
        return {
            'tag': tag,
            'commit': repo.head.commit.hexsha,
            'branch': None if repo.head.is_detached else repo.active_branch.name,
        }
    except git.exc.InvalidGitRepositoryError:
        tag = ':'.join(
            [
                os.path.basename(os.getcwd()),
                'latest',
            ]
        )
        return {'tag': f'{prefix}{tag}'}
