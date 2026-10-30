import ctypes
import os
import platform
import sys


def zero_buffer(buffer):
    """
    Overwrites the memory of a mutable buffer (such as bytearray, memoryview, or ctypes buffer)
    with zeros using platform-appropriate secure zeroing primitives to prevent compiler/interpreter
    optimization from eliding the zeroing operation.
    """
    if buffer is None:
        return

    length = len(buffer)
    if length == 0:
        return

    # Attempt OS native secure zeroing
    system = platform.system()
    zeroed_natively = False

    if system == "Windows":
        try:
            # On Windows, try RtlSecureZeroMemory via kernel32 or ntdll
            # RtlSecureZeroMemory is often an inline function in winnt.h, but RtlZeroMemory
            # is exported by kernel32 and ntdll.
            kernel32 = ctypes.windll.kernel32
            if hasattr(kernel32, "RtlSecureZeroMemory"):
                buf_type = ctypes.c_char * length
                kernel32.RtlSecureZeroMemory(buf_type.from_buffer(buffer), ctypes.c_size_t(length))
                zeroed_natively = True
            elif hasattr(kernel32, "RtlZeroMemory"):
                buf_type = ctypes.c_char * length
                kernel32.RtlZeroMemory(buf_type.from_buffer(buffer), ctypes.c_size_t(length))
                zeroed_natively = True
        except Exception:
            zeroed_natively = False
    elif system in ("Linux", "Darwin"):
        # On POSIX systems, try libc explicit_bzero, memset_s, or bzero
        try:
            libc = ctypes.CDLL(None)
            buf_type = ctypes.c_char * length
            c_buf = buf_type.from_buffer(buffer)
            if hasattr(libc, "explicit_bzero"):
                libc.explicit_bzero(c_buf, ctypes.c_size_t(length))
                zeroed_natively = True
            elif hasattr(libc, "memset_s"):
                # int memset_s(void *s, rsize_t smax, int c, rsize_t n);
                libc.memset_s(c_buf, ctypes.c_size_t(length), 0, ctypes.c_size_t(length))
                zeroed_natively = True
        except Exception:
            zeroed_natively = False

    # In all cases (or as fallback), also explicitly overwrite at the Python level
    try:
        if isinstance(buffer, (bytearray, memoryview)):
            for i in range(length):
                buffer[i] = 0
        elif hasattr(buffer, "__setitem__"):
            for i in range(length):
                buffer[i] = 0
    except Exception:
        pass


class SecureBuffer:
    """
    A context manager and byte buffer utility that manages sensitive byte data
    and provides native zeroing of memory buffers upon release or destruction.
    """

    def __init__(self, data=None, length=None):
        if data is not None:
            if isinstance(data, str):
                self._buffer = bytearray(data.encode("utf-8"))
            elif isinstance(data, (bytes, bytearray)):
                self._buffer = bytearray(data)
            else:
                self._buffer = bytearray(data)
        elif length is not None:
            self._buffer = bytearray(length)
        else:
            self._buffer = bytearray()

        self._cleared = False

    @property
    def buffer(self):
        if self._cleared:
            raise ValueError("SecureBuffer has already been zeroed and released.")
        return self._buffer

    @property
    def raw(self):
        """Returns immutable bytes snapshot without clearing."""
        if self._cleared:
            raise ValueError("SecureBuffer has already been zeroed and released.")
        return bytes(self._buffer)

    def to_bytes(self):
        return self.raw

    def __len__(self):
        return len(self._buffer)

    def __getitem__(self, item):
        if self._cleared:
            raise ValueError("SecureBuffer has already been zeroed and released.")
        return self._buffer[item]

    def __setitem__(self, key, value):
        if self._cleared:
            raise ValueError("SecureBuffer has already been zeroed and released.")
        self._buffer[key] = value

    def is_cleared(self):
        return self._cleared

    def zero(self):
        if not self._cleared and self._buffer is not None:
            zero_buffer(self._buffer)
            self._cleared = True

    def clear(self):
        self.zero()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.zero()

    def __del__(self):
        self.zero()
