import json
import pickle
from pathlib import Path

from dev.abhishekraha.secretmanager.codec import CodecUtils


def dump(data, file_name, override=False):
    if override:
        if Path(file_name).exists():
            raise FileExistsError(f"File {file_name} already exists")

    pickle.dump(data, open(file_name, "wb"))


def load(file_name):
    if not Path(file_name).exists():
        raise FileNotFoundError(f"File {file_name} does not exist")

    return pickle.load(open(file_name, "rb"))

def dump_secrets(data, file_name, override=False):
    data_bytes = json.dumps(data).encode()
    dump(data_bytes, file_name, override)

def load_secrets(file_name):
    # return CodecUtils.decrypt(load(file_name),is_file=True)
    data_bytes = load(file_name)
    return json.loads(data_bytes.decode())

