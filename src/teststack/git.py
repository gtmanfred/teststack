import os
import pathlib

import git.exc


def get_tag():
    try:
        repo = git.Repo('.')
        name = pathlib.Path(repo.remote('origin').url)
        tag = ':'.join(
            [
                name.with_suffix('').name,
                repo.head.commit.hexsha,
            ]
        )
        return {
            'tag': tag,
            'commit': repo.head.commit.hexsha,
            'branch': None if repo.head.is_detached else repo.active_branch.name,
        }
    except git.exc.InvalidGitRepositoryError:
        return {
            'tag': ':'.join(
                [
                    os.path.basename(os.getcwd()),
                    'latest',
                ]
            ),
        }
