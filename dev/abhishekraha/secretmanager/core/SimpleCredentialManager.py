import os
import time

from dev.abhishekraha.secretmanager.codec import SerDeUtils
from dev.abhishekraha.secretmanager.codec.CodecUtils import derive_key
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import APP_HOME_DIR, APP_CONFIG_DIR, SECRET_FILE, \
    SECRET_MANAGER_META_DATA
from dev.abhishekraha.secretmanager.model.SecretManagerMetaData import SecretManagerMetaData
from dev.abhishekraha.secretmanager.utils.InputUtils import secure_input

SECRETS: dict
METADATA: SecretManagerMetaData
IS_AUTHENTICATED: bool = False


def initialize():
    global SECRETS, METADATA, IS_AUTHENTICATED
    APP_HOME_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    is_app_data_exists = SECRET_FILE.exists()
    is_app_meta_data_exists = SECRET_MANAGER_META_DATA.exists()

    if not is_app_data_exists:
        SerDeUtils.dump({}, SECRET_FILE)
    SECRETS = SerDeUtils.load(SECRET_FILE)

    if not is_app_meta_data_exists:
        _initialize_metadata()
    METADATA = SerDeUtils.load(SECRET_MANAGER_META_DATA)
    user_password = secure_input("Enter master password: ")

    derive_key(user_password, METADATA.get_salt())

    try:
        if METADATA.validate_master_password(user_password):
            IS_AUTHENTICATED = True
            print("master password is valid")
        else:
            raise
    except Exception as e:
        print("master password is invalid")
        initialize()


def _initialize_metadata(re_initialize=False):
    metadata = SecretManagerMetaData()
    if not re_initialize:
        print("""
======================================================    
            Simple Credentials Manager
======================================================    

Initial Setup
        """)
    master_password = secure_input("Enter master password : ")

    metadata.set_master_password(master_password)

    validate_password = secure_input("Re-enter master password : ")

    if not metadata.validate_master_password(validate_password):
        print("Password mismatch")
        _initialize_metadata(True)

    SerDeUtils.dump(metadata, SECRET_MANAGER_META_DATA)

    time.sleep(5)
    os.system('cls' if os.name == 'nt' else 'clear')

    print("\n\n\tSetup completed.")
    print("[ NOTE ] Keep the master password handy, else all the secrets would be lost!!")
