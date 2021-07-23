from teststack.git import get_tag


def test_get_tag_isolated(runner, tag):
    with runner.isolated_filesystem():
        tag = get_tag()['tag']
        assert tag.endswith(':latest')
