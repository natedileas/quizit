import pathlib

import yaml


def load():
    file = open(pathlib.Path(__file__).parent.resolve() / "config.yaml", "r")
    data = yaml.load(file, Loader=yaml.FullLoader)
    return data
