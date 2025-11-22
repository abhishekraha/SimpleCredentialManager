import pickle
from pathlib import Path


def dump(data, file_name, override=False):
    if override:
        if Path(file_name).exists():
            raise FileExistsError(f"File {file_name} already exists")

    pickle.dump(data, open(file_name, "wb"))


def load(file_name):
    if not Path(file_name).exists():
        raise FileNotFoundError(f"File {file_name} does not exist")

    return pickle.load(open(file_name, "rb"))
