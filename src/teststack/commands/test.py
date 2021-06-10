from teststack import cli


@cli.command()
def ping():
    return "pong"
