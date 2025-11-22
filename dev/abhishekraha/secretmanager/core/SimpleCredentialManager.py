import os
import time

from dev.abhishekraha.secretmanager.codec import SerDeUtils
from dev.abhishekraha.secretmanager.codec.CodecUtils import derive_key
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import APP_HOME_DIR, APP_CONFIG_DIR, SECRET_FILE, \
    SECRET_MANAGER_META_DATA, HEADER
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import SecretManagerMetaDataManager
from dev.abhishekraha.secretmanager.utils.InputUtils import secure_input

SECRETS = {}
METADATA_MANAGER:SecretManagerMetaDataManager


def initialize():
    global SECRETS, METADATA_MANAGER
    APP_HOME_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    is_app_data_exists = SECRET_FILE.exists()
    is_app_meta_data_exists = SECRET_MANAGER_META_DATA.exists()

    if not is_app_data_exists:
        SerDeUtils.dump({}, SECRET_FILE)
    SECRETS = SerDeUtils.load(SECRET_FILE)

    if not is_app_meta_data_exists:
        _initialize_metadata()
    METADATA_MANAGER = SerDeUtils.load(SECRET_MANAGER_META_DATA)


def _initialize_metadata(re_attempt=False):
    metadata = SecretManagerMetaDataManager()
    if not re_attempt:
        print(f"{HEADER}\n\tInitial Setup")
    master_password = secure_input("Enter master password : ")

    metadata.set_master_password(master_password)

    validate_password = secure_input("Re-enter master password : ")

    if not metadata.validate_master_password(validate_password):
        print("Password mismatch")
        _initialize_metadata(True)

    SerDeUtils.dump(metadata, SECRET_MANAGER_META_DATA)

    print("\n\n\tSetup completed.")
    print("[ NOTE ] Keep the master password handy, else all the secrets would be lost!!")

    time.sleep(5)
    os.system('cls' if os.name == 'nt' else 'clear')


def authenticate(re_attempt=False):
    if not re_attempt:
        print(HEADER)
    global METADATA_MANAGER
    failsafe()
    user_password = secure_input("Enter master password: ")

    derive_key(user_password, METADATA_MANAGER.get_salt())

    try:
        if METADATA_MANAGER.validate_master_password(user_password):
            METADATA_MANAGER.reset_incorrect_password_attempts()
            return True
        else:
            raise
    except Exception as e:
        METADATA_MANAGER.increment_incorrect_password_attempts()
        print("master password is invalid")
        return authenticate(True)


def failsafe():
    global METADATA_MANAGER

    if METADATA_MANAGER.get_incorrect_password_attempts() >= METADATA_MANAGER.get_max_incorrect_password_attempts():
        print("Maximum incorrect password attempts reached. Wiping all stored passwords for security.")
        os.remove(SECRET_FILE)
        os.remove(SECRET_MANAGER_META_DATA)
        exit(1)
    elif METADATA_MANAGER.get_incorrect_password_attempts() >= METADATA_MANAGER.get_incorrect_password_threshold():
        print("Warning: Multiple incorrect password attempts detected.")
        print(
            f"Stored passwords will be wiped in {METADATA_MANAGER.get_max_incorrect_password_attempts() - METADATA_MANAGER.get_incorrect_password_attempts()} attempts.")
