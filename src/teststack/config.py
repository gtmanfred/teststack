import toml


def get_config(file_path):
    with file_path.open('r') as fh_:
        return toml.load(fh_)
