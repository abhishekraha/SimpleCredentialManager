from pathlib import Path

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
BUG_REPORT_URL = "https://github.com/abhishekraha/SimpleCredentialManager"

HEADER = """
======================================================    
            Simple Credentials Manager 
                                        v1.1.0
======================================================    
"""
