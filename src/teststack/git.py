import os
import pathlib

import git.exc


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
        return {'tag': f'{prefix}/{tag}'}
