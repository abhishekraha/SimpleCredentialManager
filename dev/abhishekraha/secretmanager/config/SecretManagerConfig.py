from pathlib import Path

USER_HOME = Path.home()
APP_HOME_DIR = Path.joinpath(USER_HOME, '.simpleCredentialManager')
APP_CONFIG_DIR = Path.joinpath(USER_HOME, '.config', '.simpleCredentialManager')
SECRET_FILE = Path(f"{APP_HOME_DIR}/.simpleCredentialManager.secret")
SECRET_MANAGER_META_DATA = Path(f"{APP_CONFIG_DIR}/.simpleCredentialManager.metadata")
DEFAULT_EXPORT_CSV = Path.joinpath(APP_HOME_DIR, 'secrets_export.csv')

HEADER = """
======================================================    
            Simple Credentials Manager 
                                        v1.0.1
======================================================    
"""
