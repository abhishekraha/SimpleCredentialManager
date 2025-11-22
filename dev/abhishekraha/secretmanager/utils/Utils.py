import os
import sys
from getpass import getpass


def secure_input(prompt):
    if sys.stdin.isatty():
        try:
            return getpass(prompt)
        except Exception:
            print("[WARNING] Your password will be visible in plain text while typing.")
            return input(prompt)
    else:
        print("[WARNING] Your password will be visible in plain text while typing.")
        return input(prompt)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
