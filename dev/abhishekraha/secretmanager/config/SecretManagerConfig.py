from pathlib import Path

APP_NAME = "Simple Credential Manager"
APP_VERSION = "v2.0.5"
APP_AUTHOR = "Abhishek Raha"
APP_COPYRIGHT = f"© 2026 {APP_AUTHOR}. All rights reserved."
APP_REPOSITORY_URL = "https://github.com/abhishekraha/SimpleCredentialManager"
APP_RELEASES_URL = f"{APP_REPOSITORY_URL}/releases/latest"
USER_HOME = Path.home()
APP_HOME_DIR = Path.joinpath(USER_HOME, '.simpleCredentialManager')
APP_CONFIG_DIR = Path.joinpath(USER_HOME, '.config', '.simpleCredentialManager')
SECRET_FILE = Path(f"{APP_HOME_DIR}/.simpleCredentialManager.secret")
SECRET_MANAGER_META_DATA = Path(f"{APP_CONFIG_DIR}/.simpleCredentialManager.metadata")
AUDIT_LOG_FILE = Path(f"{APP_CONFIG_DIR}/.simpleCredentialManager.audit.log")
DEFAULT_EXPORT_CSV = Path.joinpath(APP_HOME_DIR, 'secrets_export.csv')
RELEASE_STATUS_CACHE_FILE = Path(f"{APP_CONFIG_DIR}/.simpleCredentialManager.release-status.json")

FAILED_AUTH_LOCKOUT_THRESHOLD = 3
FAILED_AUTH_LOCKOUT_BASE_SECONDS = 30
FAILED_AUTH_LOCKOUT_MAX_SECONDS = 900
SESSION_IDLE_LOCK_SECONDS = 60
RELEASE_UPDATE_API_URL = "https://api.github.com/repos/abhishekraha/SimpleCredentialManager/releases/latest"
RELEASE_STATUS_CACHE_TTL_SECONDS = 21600
RELEASE_STALE_AFTER_DAYS = 30
RELEASE_UPDATE_REQUEST_TIMEOUT_SECONDS = 5
CLI_RELEASE_WARNING_SECONDS = 10
BUG_REPORT_URL = "https://github.com/abhishekraha/SimpleCredentialManager/issues"

HEADER = f"""
======================================================    
            Simple Credentials Manager
                                        {APP_VERSION}
======================================================    
"""
