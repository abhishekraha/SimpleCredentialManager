from pathlib import Path

APP_NAME = "Simple Credential Manager"
APP_VERSION = "v2.0.1"
APP_AUTHOR = "Abhishek Raha"
APP_COPYRIGHT = f"© 2026 ${APP_AUTHOR}. All rights reserved."
APP_REPOSITORY_URL = "https://github.com/abhishekraha/SimpleCredentialManager"
USER_HOME = Path.home()
APP_HOME_DIR = Path.joinpath(USER_HOME, '.simpleCredentialManager')
APP_CONFIG_DIR = Path.joinpath(USER_HOME, '.config', '.simpleCredentialManager')
SECRET_FILE = Path(f"{APP_HOME_DIR}/.simpleCredentialManager.secret")
SECRET_MANAGER_META_DATA = Path(f"{APP_CONFIG_DIR}/.simpleCredentialManager.metadata")
AUDIT_LOG_FILE = Path(f"{APP_CONFIG_DIR}/.simpleCredentialManager.audit.log")
DEFAULT_EXPORT_CSV = Path.joinpath(APP_HOME_DIR, 'secrets_export.csv')

FAILED_AUTH_LOCKOUT_THRESHOLD = 3
FAILED_AUTH_LOCKOUT_BASE_SECONDS = 30
FAILED_AUTH_LOCKOUT_MAX_SECONDS = 900
BUG_REPORT_URL = "https://github.com/abhishekraha/SimpleCredentialManager/issues"

HEADER = f"""
======================================================    
            Simple Credentials Manager
                                        ${APP_VERSION}
======================================================    
"""
