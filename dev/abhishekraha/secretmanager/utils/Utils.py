import os
import platform
import shutil
import subprocess
import sys
import time
from getpass import getpass


class IdleTimeoutError(TimeoutError):
    pass


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


def timed_input(prompt, timeout_seconds):
    return _timed_terminal_input(prompt, timeout_seconds, secure=False)


def timed_secure_input(prompt, timeout_seconds):
    return _timed_terminal_input(prompt, timeout_seconds, secure=True)


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


def _timed_terminal_input(prompt, timeout_seconds, secure):
    if timeout_seconds is None or timeout_seconds <= 0:
        return secure_input(prompt) if secure else input(prompt)

    if not sys.stdin.isatty():
        return secure_input(prompt) if secure else input(prompt)

    if os.name == "nt":
        return _windows_timed_input(prompt, timeout_seconds, secure)
    return _posix_timed_input(prompt, timeout_seconds, secure)


def _windows_timed_input(prompt, timeout_seconds, secure):
    import msvcrt

    return _timed_character_input(
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        secure=secure,
        key_available=msvcrt.kbhit,
        read_character=msvcrt.getwch,
    )


def _posix_timed_input(prompt, timeout_seconds, secure):
    import select
    import termios
    import tty

    file_descriptor = sys.stdin.fileno()
    previous_terminal_state = termios.tcgetattr(file_descriptor)

    def key_available(timeout_value):
        readable, _, _ = select.select([file_descriptor], [], [], timeout_value)
        return bool(readable)

    def read_character():
        return sys.stdin.read(1)

    sys.stdout.write(prompt)
    sys.stdout.flush()
    buffer = []
    deadline = time.monotonic() + timeout_seconds

    try:
        tty.setraw(file_descriptor)
        while True:
            remaining_seconds = max(0, deadline - time.monotonic())
            if remaining_seconds == 0 or not key_available(remaining_seconds):
                sys.stdout.write("\n")
                sys.stdout.flush()
                raise IdleTimeoutError("Input timed out due to inactivity.")

            character = read_character()
            deadline = time.monotonic() + timeout_seconds
            outcome = _handle_character(character, buffer, secure)
            if outcome is None:
                continue
            return outcome
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, previous_terminal_state)


def _timed_character_input(prompt, timeout_seconds, secure, key_available, read_character):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    buffer = []
    deadline = time.monotonic() + timeout_seconds

    while True:
        if key_available():
            character = read_character()
            deadline = time.monotonic() + timeout_seconds

            if character in ("\x00", "\xe0"):
                read_character()
                continue

            outcome = _handle_character(character, buffer, secure)
            if outcome is None:
                continue
            return outcome

        if time.monotonic() >= deadline:
            sys.stdout.write("\n")
            sys.stdout.flush()
            raise IdleTimeoutError("Input timed out due to inactivity.")

        time.sleep(0.05)


def _handle_character(character, buffer, secure):
    if character in ("\r", "\n"):
        sys.stdout.write("\n")
        sys.stdout.flush()
        return "".join(buffer)

    if character == "\x03":
        raise KeyboardInterrupt

    if character == "\x04" and not buffer:
        raise EOFError

    if character in ("\b", "\x7f"):
        if buffer:
            buffer.pop()
            if not secure:
                sys.stdout.write("\b \b")
                sys.stdout.flush()
        return None

    if ord(character) < 32 and character != "\t":
        return None

    buffer.append(character)
    if not secure:
        sys.stdout.write(character)
        sys.stdout.flush()
    return None
