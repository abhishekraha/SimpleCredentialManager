import os
import time
from datetime import datetime

from dev.abhishekraha.secretmanager.codec import SerDeUtils
from dev.abhishekraha.secretmanager.codec.CodecUtils import derive_key
from dev.abhishekraha.secretmanager.config.SecretManagerConfig import APP_HOME_DIR, APP_CONFIG_DIR, SECRET_FILE, \
    SECRET_MANAGER_META_DATA, HEADER
from dev.abhishekraha.secretmanager.model.Secret import create_secret
from dev.abhishekraha.secretmanager.model.SecretManagerMetaDataManager import SecretManagerMetaDataManager
from dev.abhishekraha.secretmanager.utils.Utils import secure_input, clear_screen

SECRETS = {}
METADATA_MANAGER: SecretManagerMetaDataManager


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
    clear_screen()


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


def add_secret():
    secret_name = input("Enter a name for the secret: ")
    if secret_name in SECRETS.keys():
        print("A secret with this name already exists. Please choose a different name or update option.")
        return
    secret = create_secret(secret_name)
    SECRETS[secret_name] = secret
    SerDeUtils.dump(SECRETS, SECRET_FILE)
    print("Secret added successfully.")


def view_secret():
    secret_name = input("Enter the name of the secret to view: ")
    secret = SECRETS.get(secret_name)
    if secret:
        print(secret.peak())
    else:
        print("Secret not found.")


def update_secret():
    secret_name = input("Enter the name of the secret to update: ")
    secret = SECRETS.get(secret_name)
    if secret:
        print("Leave a field blank to keep it unchanged.")
        username = input(f"Enter new username (current: {secret.get_username()}): ") or secret.get_username()
        password = secure_input("Enter new password (leave blank to keep unchanged): ") or secret.get_password()
        url = input(f"Enter new URL (current: {secret.get_url()}): ") or secret.get_url()
        comments = input(f"Enter new comments (current: {secret.get_comments()}): ") or secret.get_comments()

        secret.set_username(username)
        secret.set_password(password)
        secret.set_url(url)
        secret.set_comments(comments)
        secret.set_update_date(datetime.now())

        SerDeUtils.dump(SECRETS, SECRET_FILE)
        print("Secret updated successfully.")
    else:
        print("Secret not found.")


def delete_secret():
    secret_name = input("Enter the name of the secret to delete: ")
    if secret_name in SECRETS:
        del SECRETS[secret_name]
        SerDeUtils.dump(SECRETS, SECRET_FILE)
        print("Secret deleted successfully.")
    else:
        print("Secret not found.")


def list_secrets():
    if SECRETS:
        print("Stored Secrets:")
        for name in SECRETS.keys():
            print(f"- {name}")
    else:
        print("No secrets stored.")


def show_menu():
    print("\nMenu:")
    print("1. Add Secret")
    print("2. View Secret")
    print("3. Update Secret")
    print("4. Delete Secret")
    print("5. List All Secrets")
    print("6. Exit")


def get_menu():
    return {
        '1': add_secret,
        '2': view_secret,
        '3': update_secret,
        '4': delete_secret,
        '5': list_secrets,
        '6': exit
    }
