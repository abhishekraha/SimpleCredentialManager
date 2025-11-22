import sys
from getpass import getpass

import pwinput


def secure_input(prompt):
    if sys.stdin.isatty():
        try:
            return getpass(prompt)
        except Exception:
            return pwinput.pwinput(prompt, mask="*")
    else:
        return pwinput.pwinput(prompt, mask="*")
