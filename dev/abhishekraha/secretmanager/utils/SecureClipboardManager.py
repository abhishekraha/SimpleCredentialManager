import hashlib
import hmac
import os
import platform
import shutil
import subprocess
import threading
import time


_SESSION_HMAC_KEY = os.urandom(32)


def _calculate_hash(text):
    """
    Computes a keyed HMAC token for clipboard change comparison.
    Using HMAC with a per-process session key avoids CodeQL weak password hashing
    flags because this is an ephemeral verification token, not a stored password hash.
    """
    if text is None:
        return None
    return hmac.new(_SESSION_HMAC_KEY, text.encode("utf-8"), hashlib.sha256).hexdigest()


def _set_windows_clipboard_with_privacy(text):
    """
    Sets the Windows clipboard text and registers/sets the
    ExcludeClipboardContentFromMonitorProcessing format so that Windows 10/11
    Win+V clipboard history and cloud sync ignore this item.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Set function signatures for 64-bit safety
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

    user32.OpenClipboard.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    format_name = "ExcludeClipboardContentFromMonitorProcessing"
    exclude_format = user32.RegisterClipboardFormatW(format_name)

    opened = False
    for _ in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)

    if not opened:
        raise OSError("Unable to open Windows clipboard")

    try:
        user32.EmptyClipboard()

        # 1. Set the CF_UNICODETEXT payload
        text_utf16 = (text + "\0").encode("utf-16le")
        h_text_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_utf16))
        if not h_text_mem:
            raise MemoryError("GlobalAlloc failed for clipboard text")
        ptr = kernel32.GlobalLock(h_text_mem)
        ctypes.memmove(ptr, text_utf16, len(text_utf16))
        kernel32.GlobalUnlock(h_text_mem)
        if not user32.SetClipboardData(CF_UNICODETEXT, h_text_mem):
            kernel32.GlobalFree(h_text_mem)
            raise OSError("SetClipboardData failed for CF_UNICODETEXT")

        # 2. Set ExcludeClipboardContentFromMonitorProcessing flag (DWORD value = 1)
        if exclude_format:
            flag_bytes = (1).to_bytes(4, byteorder="little")
            h_flag_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(flag_bytes))
            if h_flag_mem:
                ptr = kernel32.GlobalLock(h_flag_mem)
                ctypes.memmove(ptr, flag_bytes, len(flag_bytes))
                kernel32.GlobalUnlock(h_flag_mem)
                if not user32.SetClipboardData(exclude_format, h_flag_mem):
                    kernel32.GlobalFree(h_flag_mem)

        return True
    finally:
        user32.CloseClipboard()


def _set_macos_clipboard_with_privacy(text):
    """
    On macOS, sets the pasteboard text with org.nspasteboard.ConcealedType
    via osascript or pbcopy.
    """
    script = f'''
    use framework "Foundation"
    use framework "AppKit"
    set pb to current application's NSPasteboard's generalPasteboard()
    pb's clearContents()
    pb's setString:({subprocess.list2cmdline([text])}) forType:(current application's NSPasteboardTypeString)
    pb's setString:"" forType:"org.nspasteboard.ConcealedType"
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=2)
        if res.returncode == 0:
            return True
    except Exception:
        pass

    res = subprocess.run(["pbcopy"], input=text, text=True, check=True, capture_output=True)
    return res.returncode == 0


def _set_linux_clipboard_with_privacy(text):
    """
    On Linux, uses wl-copy or xclip, setting mime type x-kde-passwordManagerHint = "secret" if supported.
    """
    if shutil.which("wl-copy"):
        try:
            subprocess.run(
                ["wl-copy", "--type", "x-kde-passwordManagerHint", "secret", text],
                check=True,
                capture_output=True,
                timeout=2,
            )
            subprocess.run(["wl-copy", text], check=True, capture_output=True, timeout=2)
            return True
        except Exception:
            pass

    if shutil.which("xclip"):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                check=True,
                capture_output=True,
                timeout=2,
            )
            return True
        except Exception:
            pass

    if shutil.which("xsel"):
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text,
                text=True,
                check=True,
                capture_output=True,
                timeout=2,
            )
            return True
        except Exception:
            pass

    return False


def get_current_clipboard_text():
    """Reads current plain text from system clipboard using platform mechanisms or tkinter."""
    system = platform.system()
    if system == "Windows":
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            CF_UNICODETEXT = 13

            user32.OpenClipboard.restype = wintypes.BOOL
            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.argtypes = []
            user32.GetClipboardData.restype = wintypes.HANDLE
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

            opened = False
            for _ in range(5):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.01)

            if opened:
                try:
                    h_data = user32.GetClipboardData(CF_UNICODETEXT)
                    if h_data:
                        ptr = kernel32.GlobalLock(h_data)
                        if ptr:
                            try:
                                return ctypes.c_wchar_p(ptr).value
                            finally:
                                kernel32.GlobalUnlock(h_data)
                    return ""
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

    # Fallback using tkinter
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            content = root.clipboard_get()
            return content
        except Exception:
            return ""
        finally:
            root.destroy()
    except Exception:
        pass

    return None


def clear_system_clipboard():
    """Empties the system clipboard."""
    system = platform.system()
    if system == "Windows":
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.argtypes = []
            user32.EmptyClipboard.restype = wintypes.BOOL
            user32.EmptyClipboard.argtypes = []

            opened = False
            for _ in range(5):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.01)
            if opened:
                try:
                    user32.EmptyClipboard()
                    return True
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

    # Fallback using tkinter or commands
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.update()
        root.destroy()
        return True
    except Exception:
        pass

    return False


class SecureClipboardManager:
    """
    Manages secure clipboard copies with timed auto-clearing and OS privacy flags.
    Prevents clipboard history daemons (like Windows 10/11 Win+V) from capturing secrets,
    and only clears the clipboard after timeout if the clipboard still contains the copied secret.
    """

    DEFAULT_CLEAR_TIMEOUT_SECONDS = 30

    _active_timer = None
    _lock = threading.Lock()
    _active_hash = None

    @classmethod
    def copy(cls, text, clear_timeout_seconds=DEFAULT_CLEAR_TIMEOUT_SECONDS, enable_privacy=True):
        """
        Copies text to clipboard with privacy flags and starts a background auto-clear timer.
        """
        clipboard_text = "" if text is None else str(text)
        copied_hash = _calculate_hash(clipboard_text)

        success = False
        system = platform.system()

        if enable_privacy:
            try:
                if system == "Windows":
                    success = _set_windows_clipboard_with_privacy(clipboard_text)
                elif system == "Darwin":
                    success = _set_macos_clipboard_with_privacy(clipboard_text)
                elif system == "Linux":
                    success = _set_linux_clipboard_with_privacy(clipboard_text)
            except Exception:
                success = False

        if not success:
            success = cls._fallback_copy(clipboard_text)

        if success and clear_timeout_seconds and clear_timeout_seconds > 0:
            cls._schedule_auto_clear(copied_hash, clear_timeout_seconds)

        return success

    @classmethod
    def _fallback_copy(cls, clipboard_text):
        system = platform.system()
        if system == "Windows":
            commands = [["clip"]]
        elif system == "Darwin":
            commands = [["pbcopy"]]
        else:
            commands = [
                cmd for cmd in [
                    ["wl-copy"],
                    ["xclip", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--input"],
                ] if shutil.which(cmd[0])
            ]

        for command in commands:
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

    @classmethod
    def _schedule_auto_clear(cls, expected_hash, timeout_seconds):
        with cls._lock:
            cls._active_hash = expected_hash
            if cls._active_timer is not None and hasattr(cls._active_timer, "cancel"):
                cls._active_timer.cancel()

            timer = threading.Timer(
                timeout_seconds,
                cls._on_timer_fired,
                args=(expected_hash,),
            )
            timer.daemon = True
            cls._active_timer = timer
            timer.start()

    @classmethod
    def _on_timer_fired(cls, expected_hash):
        with cls._lock:
            if cls._active_hash != expected_hash:
                return
            current_text = get_current_clipboard_text()
            if current_text is not None and _calculate_hash(current_text) == expected_hash:
                clear_system_clipboard()
            cls._active_hash = None
            cls._active_timer = None

    @classmethod
    def cancel_active_timer(cls):
        with cls._lock:
            if cls._active_timer is not None and hasattr(cls._active_timer, "cancel"):
                cls._active_timer.cancel()
            cls._active_hash = None
            cls._active_timer = None
