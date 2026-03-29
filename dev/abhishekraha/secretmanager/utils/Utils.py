import os
import platform
import shutil
import subprocess
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


def copy_to_clipboard(value):
    clipboard_text = "" if value is None else str(value)
    clipboard_commands = _get_clipboard_commands()

    for command in clipboard_commands:
        try:
            subprocess.run(
                command,
                input=clipboard_text,
                text=True,
                check=True,
                capture_output=True,
            )
            return True
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            continue

    return _copy_with_tkinter(clipboard_text)


def _get_clipboard_commands():
    operating_system = platform.system()
    if operating_system == "Windows":
        return [["clip"]]
    if operating_system == "Darwin":
        return [["pbcopy"]]

    linux_commands = [
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]
    return [command for command in linux_commands if shutil.which(command[0])]


def _copy_with_tkinter(clipboard_text):
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(clipboard_text)
        root.update()
        root.destroy()
        return True
    except Exception:
        return False
