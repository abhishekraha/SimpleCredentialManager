import hashlib
import urllib.error
import urllib.request


HIBP_API_URL = "https://api.pwnedpasswords.com/range/{prefix}"
DEFAULT_TIMEOUT_SECONDS = 3


def check_password_breach(password, timeout=DEFAULT_TIMEOUT_SECONDS):
    """
    Checks if a password has appeared in known data breaches using HaveIBeenPwned's
    k-anonymity API model.

    Privacy-preserving: Only the first 5 hexadecimal characters of the SHA-1 hash of the
    password are transmitted to the API. The full hash or plaintext never leaves the device.

    Returns:
        tuple (is_breached: bool, breach_count: int)
        If the network request fails or times out, returns (False, 0).
    """
    if not password:
        return False, 0

    # Calculate SHA-1 hash of the password as required by HaveIBeenPwned Range API protocol.
    # Note: CodeQL flagging this as weak hash is a false positive for storage, because this is NOT
    # used for password storage or verification, but for HaveIBeenPwned's external k-anonymity protocol.
    # usedforsecurity=False tells Python and linters this is not used as a security storage primitive.
    sha1_hex = hashlib.new("sha1", password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix = sha1_hex[:5]
    suffix = sha1_hex[5:]

    url = HIBP_API_URL.format(prefix=prefix)
    headers = {
        "User-Agent": "SimpleCredentialManager-SecurityChecker",
        "Add-Padding": "true",  # Prevent response size side-channel analysis
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return False, 0
            body = response.read().decode("utf-8", errors="ignore")

        # Parse the response lines: <hash_suffix>:<count>
        for line in body.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            entry_suffix, count_str = line.split(":", 1)
            if entry_suffix.strip() == suffix:
                try:
                    count = int(count_str.strip())
                    return True, count
                except ValueError:
                    return True, 1

        return False, 0

    except Exception:
        # Gracefully handle network unavailability, timeouts, or errors
        return False, 0
