import math
import re


COMMON_PATTERNS = [
    r"^[0-9]+$",                         # only digits
    r"^[a-zA-Z]+$",                      # only letters
    r"^(.)\1+$",                         # all identical characters (e.g. aaaaa)
    r"(?i)(password|admin|root|qwerty|welcome|123456|secret|login)",
]

COMMON_SEQUENCES = [
    "abcdefghijklmnopqrstuvwxyz",
    "01234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
]


def calculate_entropy(password):
    """
    Calculates the Shannon entropy (in bits) of the password based on
    character diversity and length.
    """
    if not password:
        return 0.0

    length = len(password)
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)

    charset_size = 0
    if has_lower:
        charset_size += 26
    if has_upper:
        charset_size += 26
    if has_digit:
        charset_size += 10
    if has_symbol:
        charset_size += 33

    if charset_size == 0:
        return 0.0

    # Theoretical pool entropy = length * log2(charset_size)
    pool_entropy = length * math.log2(charset_size)

    # Shannon frequency entropy = -sum(p * log2(p)) * length
    char_counts = {}
    for char in password:
        char_counts[char] = char_counts.get(char, 0) + 1

    shannon_entropy_per_char = 0.0
    for count in char_counts.values():
        p = count / length
        shannon_entropy_per_char -= p * math.log2(p)
    shannon_entropy = shannon_entropy_per_char * length

    # Blend entropy metric (take the conservative min)
    return round(min(pool_entropy, shannon_entropy * 1.5), 2)


def has_sequential_chars(password, min_length=4):
    """Checks if password contains incremental or decremental sequences of length >= min_length."""
    pwd_lower = password.lower()
    for seq in COMMON_SEQUENCES:
        for i in range(len(seq) - min_length + 1):
            sub = seq[i : i + min_length]
            if sub in pwd_lower or sub[::-1] in pwd_lower:
                return True
    return False


def estimate_password_strength(password):
    """
    Evaluates password strength and returns a dict with:
    - score: integer from 0 (very weak) to 4 (very strong)
    - entropy: float bits
    - label: 'Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'
    - suggestions: list of improvement suggestions
    """
    if not password:
        return {
            "score": 0,
            "entropy": 0.0,
            "label": "Very Weak",
            "suggestions": ["Password cannot be empty."],
        }

    length = len(password)
    entropy = calculate_entropy(password)
    suggestions = []

    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)

    if length < 8:
        suggestions.append("Increase password length to at least 8 characters.")
    if not has_lower:
        suggestions.append("Add lowercase letters.")
    if not has_upper:
        suggestions.append("Add uppercase letters.")
    if not has_digit:
        suggestions.append("Add numbers.")
    if not has_symbol:
        suggestions.append("Add special symbols.")

    for pattern in COMMON_PATTERNS:
        if re.search(pattern, password):
            suggestions.append("Avoid common dictionary words, simple repetitions, or predictable patterns.")
            break

    if has_sequential_chars(password):
        suggestions.append("Avoid sequential character sequences (e.g., '1234', 'abcd').")

    # Score calculation
    if length < 6 or entropy < 25:
        score = 0
    elif length < 8 or entropy < 40 or len(suggestions) >= 4:
        score = 1
    elif entropy < 55 or len(suggestions) >= 2:
        score = 2
    elif entropy < 75 or len(suggestions) >= 1:
        score = 3
    else:
        score = 4

    labels = {
        0: "Very Weak",
        1: "Weak",
        2: "Fair",
        3: "Strong",
        4: "Very Strong",
    }

    return {
        "score": score,
        "entropy": entropy,
        "label": labels[score],
        "suggestions": suggestions,
    }


def validate_master_password_policy(password, min_length=8, min_entropy=30.0):
    """
    Enforces minimum security policy for master passwords.
    Returns (is_valid, error_message).
    """
    if not password:
        return False, "Master password cannot be empty."

    if len(password) < min_length:
        return False, f"Master password must be at least {min_length} characters long."

    strength = estimate_password_strength(password)
    if strength["entropy"] < min_entropy:
        return (
            False,
            f"Master password is too weak ({strength['label']}, entropy {strength['entropy']} bits). "
            + " ".join(strength["suggestions"]),
        )

    # Check for simple identical repetitions
    if len(set(password)) <= 2 and len(password) > 4:
        return False, "Master password contains too few distinct characters."

    return True, None
