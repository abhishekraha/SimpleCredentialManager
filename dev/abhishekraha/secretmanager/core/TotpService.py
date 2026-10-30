import base64
import hashlib
import hmac
import re
import struct
import time
from urllib.parse import parse_qs, unquote, urlparse


class TotpService:
    """
    TOTP Engine compliant with RFC 6238 / RFC 4226.
    Computes current 6-digit TOTP codes and remaining seconds in 30-second windows.
    Accepts raw Base32 secrets or otpauth:// URIs.
    """

    DEFAULT_STEP_SECONDS = 30
    DEFAULT_DIGITS = 6

    @classmethod
    def parse_secret(cls, raw_secret_or_uri):
        """
        Parses either a raw Base32 secret string or an otpauth://totp/ URI.
        Returns the sanitized, uppercase Base32 secret string without whitespace.
        If empty or invalid, returns empty string or raises ValueError.
        """
        if not raw_secret_or_uri:
            return ""

        input_str = str(raw_secret_or_uri).strip()
        if not input_str:
            return ""

        # Check if URI format: otpauth://totp/...
        if input_str.lower().startswith("otpauth://"):
            parsed = urlparse(input_str)
            query_params = parse_qs(parsed.query)
            secret_candidates = query_params.get("secret", [])
            if not secret_candidates or not secret_candidates[0].strip():
                raise ValueError("otpauth URI does not contain a valid secret parameter.")
            raw_secret = secret_candidates[0].strip()
        else:
            raw_secret = input_str

        # Clean secret: remove spaces and hyphens, uppercase
        clean_secret = re.sub(r"[\s\-]+", "", raw_secret).upper()
        # Validate Base32 character set (A-Z, 2-7, optional padding '=')
        if not re.match(r"^[A-Z2-7]+=*$", clean_secret):
            raise ValueError("Invalid Base32 secret encoding.")

        return clean_secret

    @classmethod
    def parse_uri_metadata(cls, uri_string):
        """
        Extracts metadata from an otpauth://totp/ URI if available.
        Returns dict with keys: 'label', 'issuer', 'secret', 'algorithm', 'digits', 'period'.
        """
        if not uri_string or not str(uri_string).strip().lower().startswith("otpauth://"):
            return None

        parsed = urlparse(uri_string.strip())
        label = unquote(parsed.path.lstrip("/"))
        params = parse_qs(parsed.query)

        issuer = params.get("issuer", [""])[0]
        secret = params.get("secret", [""])[0]
        algorithm = params.get("algorithm", ["SHA1"])[0].upper()
        digits = int(params.get("digits", [cls.DEFAULT_DIGITS])[0])
        period = int(params.get("period", [cls.DEFAULT_STEP_SECONDS])[0])

        return {
            "label": label,
            "issuer": issuer,
            "secret": secret,
            "algorithm": algorithm,
            "digits": digits,
            "period": period,
        }

    @classmethod
    def get_remaining_seconds(cls, timestamp=None, step=DEFAULT_STEP_SECONDS):
        """
        Calculates remaining seconds in the current 30-second window.
        """
        current_time = time.time() if timestamp is None else float(timestamp)
        return int(step - (current_time % step))

    @classmethod
    def generate_totp(
        cls,
        secret_or_uri,
        timestamp=None,
        step=DEFAULT_STEP_SECONDS,
        digits=DEFAULT_DIGITS,
        algorithm="sha1",
    ):
        """
        Generates the current TOTP code and remaining seconds.

        Returns:
            dict with:
                - code: 6-digit string (e.g. '123456')
                - formatted_code: spaced format (e.g. '123 456')
                - remaining_seconds: integer (1-30)
                - progress: float between 0.0 and 1.0 (proportion of step elapsed)
        """
        clean_secret = cls.parse_secret(secret_or_uri)
        if not clean_secret:
            raise ValueError("Secret cannot be empty.")

        # Ensure correct Base32 padding with '='
        missing_padding = len(clean_secret) % 8
        if missing_padding != 0:
            clean_secret += "=" * (8 - missing_padding)

        try:
            key_bytes = base64.b32decode(clean_secret, casefold=True)
        except Exception as exc:
            raise ValueError(f"Failed to decode Base32 secret: {exc}") from exc

        current_time = time.time() if timestamp is None else float(timestamp)
        counter = int(current_time // step)
        counter_bytes = struct.pack(">Q", counter)

        # Hash algorithm selection
        hash_algo = getattr(hashlib, algorithm.lower(), hashlib.sha1)

        # Compute HMAC
        hmac_digest = hmac.new(key_bytes, counter_bytes, hash_algo).digest()

        # Dynamic truncation (RFC 4226 Section 5.4)
        offset = hmac_digest[-1] & 0x0F
        code_int = (
            ((hmac_digest[offset] & 0x7F) << 24)
            | ((hmac_digest[offset + 1] & 0xFF) << 16)
            | ((hmac_digest[offset + 2] & 0xFF) << 8)
            | (hmac_digest[offset + 3] & 0xFF)
        )

        modulus = 10**digits
        raw_code = str(code_int % modulus).zfill(digits)

        # Format code (e.g. '123 456' for 6 digits)
        if digits == 6:
            formatted_code = f"{raw_code[:3]} {raw_code[3:]}"
        elif digits == 8:
            formatted_code = f"{raw_code[:4]} {raw_code[4:]}"
        else:
            formatted_code = raw_code

        remaining_seconds = cls.get_remaining_seconds(current_time, step=step)
        progress = (step - remaining_seconds) / float(step)

        return {
            "code": raw_code,
            "formatted_code": formatted_code,
            "remaining_seconds": remaining_seconds,
            "progress": progress,
        }

    @classmethod
    def verify_totp(
        cls,
        secret_or_uri,
        candidate_code,
        window=1,
        step=DEFAULT_STEP_SECONDS,
        digits=DEFAULT_DIGITS,
    ):
        """
        Verifies a user-supplied candidate TOTP code against the secret,
        allowing a drift window of +/- window steps (default 1 step = +/-30s).
        """
        if not candidate_code:
            return False

        candidate_clean = re.sub(r"\s+", "", str(candidate_code)).strip()
        now = time.time()

        for delta in range(-window, window + 1):
            t = now + (delta * step)
            try:
                res = cls.generate_totp(secret_or_uri, timestamp=t, step=step, digits=digits)
                if hmac.compare_digest(res["code"], candidate_clean):
                    return True
            except ValueError:
                return False

        return False
