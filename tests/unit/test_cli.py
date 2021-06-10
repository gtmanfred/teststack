import sys

from teststack import import_commands


def test_import_commands():
    import_commands()
    assert "teststack.commands.containers" in sys.modules
    assert "teststack.commands.env" in sys.modules
