from collections import defaultdict
from datetime import datetime, timezone

from dev.abhishekraha.secretmanager.utils.BreachChecker import check_password_breach
from dev.abhishekraha.secretmanager.utils.PasswordStrengthUtils import (
    calculate_entropy,
    estimate_password_strength,
)


class PasswordHealthService:
    """
    Vault Health & Security Audit Engine.
    Evaluates:
    - Overall Vault Health Score (0 - 100)
    - Weak passwords (entropy < 45 bits or length < 12 characters)
    - Reused / duplicate passwords across secrets
    - Stale passwords (> 365 days unrotated)
    - Optional HaveIBeenPwned k-anonymity breach check
    """

    STALE_THRESHOLD_DAYS = 365
    WEAK_LENGTH_THRESHOLD = 12
    WEAK_ENTROPY_THRESHOLD = 45.0

    @classmethod
    def audit_vault(cls, secrets_list, check_breaches=False, breach_timeout=3):
        """
        Performs a full audit of the provided secrets list (or iterable of Secret objects / dicts).

        Parameters:
            secrets_list: iterable of Secret objects (or dictionaries with name, password, create_date, update_date)
            check_breaches: bool, whether to run HaveIBeenPwned k-anonymity checks
            breach_timeout: timeout in seconds per breach request

        Returns:
            dict containing:
                - health_score: int (0 to 100)
                - total_secrets: int
                - weak_secrets: list of dicts {name, username, length, entropy, reason}
                - reused_secrets: list of dicts {password_mask, count, secret_names}
                - stale_secrets: list of dicts {name, age_days, last_modified}
                - breached_secrets: list of dicts {name, breach_count} (if check_breaches=True)
                - category_breakdown: dict {category: count}
                - summary: dict with aggregate counts
        """
        secrets = list(secrets_list or [])
        total_secrets = len(secrets)

        if total_secrets == 0:
            return {
                "health_score": 100,
                "total_secrets": 0,
                "weak_secrets": [],
                "reused_secrets": [],
                "stale_secrets": [],
                "breached_secrets": [],
                "category_breakdown": {},
                "summary": {
                    "total": 0,
                    "weak_count": 0,
                    "reused_count": 0,
                    "stale_count": 0,
                    "breached_count": 0,
                },
            }

        weak_secrets = []
        stale_secrets = []
        breached_secrets = []
        password_to_secrets = defaultdict(list)
        category_counts = defaultdict(int)

        now = datetime.now(timezone.utc)

        for secret in secrets:
            # Handle both Secret model instances and dictionaries
            if hasattr(secret, "get_name"):
                name = secret.get_name()
                username = secret.get_username()
                password = secret.get_password()
                create_date = secret.get_create_date()
                update_date = secret.get_update_date()
                category = getattr(secret, "get_category", lambda: "login")()
            else:
                name = secret.get("name", "")
                username = secret.get("username", "")
                password = secret.get("password", "")
                create_date = secret.get("created_at") or secret.get("create_date")
                update_date = secret.get("updated_at") or secret.get("update_date")
                category = secret.get("category", "login")

            category_counts[category or "login"] += 1

            # 1. Weakness check
            is_weak, reason, entropy = cls.is_weak_password(password)
            if is_weak:
                weak_secrets.append({
                    "name": name,
                    "username": username,
                    "length": len(password or ""),
                    "entropy": entropy,
                    "reason": reason,
                })

            # Track for duplicate / reuse check
            if password:
                password_to_secrets[password].append(name)

            # 2. Staleness check
            effective_date = update_date or create_date
            age_days = cls._compute_age_days(effective_date, now)
            if age_days is not None and age_days > cls.STALE_THRESHOLD_DAYS:
                stale_secrets.append({
                    "name": name,
                    "age_days": age_days,
                    "last_modified": effective_date.isoformat() if hasattr(effective_date, "isoformat") else str(effective_date),
                })

        # 3. Breach check (optional) - Deduplicate queries by password prefix to make batch scanning instant
        if check_breaches:
            # Group unique passwords to prevent duplicate HTTP queries
            unique_passwords = {}
            for secret in secrets_list:
                if isinstance(secret, dict):
                    name = secret.get("name") or "Unnamed"
                    pwd = secret.get("password") or ""
                else:
                    name = secret.get_name() or "Unnamed"
                    pwd = secret.get_password() or ""
                if pwd:
                    unique_passwords.setdefault(pwd, []).append(name)

            for pwd, names in unique_passwords.items():
                is_pwned, count = check_password_breach(pwd, timeout=breach_timeout)
                if is_pwned:
                    for name in names:
                        breached_secrets.append({
                            "name": name,
                            "breach_count": count,
                        })

        # 4. Duplicate / reused passwords
        reused_secrets = []
        reused_secret_count = 0
        for pwd, names in password_to_secrets.items():
            if len(names) > 1:
                reused_secret_count += len(names)
                # Mask password for display
                masked = pwd[0] + ("*" * max(1, len(pwd) - 2)) + (pwd[-1] if len(pwd) > 1 else "")
                reused_secrets.append({
                    "password_mask": masked,
                    "count": len(names),
                    "secret_names": sorted(names),
                })

        # Calculate Vault Health Score (0 - 100)
        health_score = cls.calculate_health_score(
            total_secrets=total_secrets,
            weak_count=len(weak_secrets),
            reused_count=reused_secret_count,
            stale_count=len(stale_secrets),
            breached_count=len(breached_secrets),
        )

        return {
            "health_score": health_score,
            "total_secrets": total_secrets,
            "weak_secrets": weak_secrets,
            "reused_secrets": reused_secrets,
            "stale_secrets": stale_secrets,
            "breached_secrets": breached_secrets,
            "category_breakdown": dict(category_counts),
            "summary": {
                "total": total_secrets,
                "weak_count": len(weak_secrets),
                "reused_count": reused_secret_count,
                "stale_count": len(stale_secrets),
                "breached_count": len(breached_secrets),
            },
        }

    @classmethod
    def is_weak_password(cls, password):
        """
        Determines whether a password is weak based on length (< 12) or entropy (< 45 bits).
        Returns tuple: (is_weak: bool, reason: str, entropy: float)
        """
        if not password:
            return True, "Empty password", 0.0

        length = len(password)
        entropy = calculate_entropy(password)

        if length < cls.WEAK_LENGTH_THRESHOLD:
            return True, f"Too short ({length} < {cls.WEAK_LENGTH_THRESHOLD} characters)", entropy

        if entropy < cls.WEAK_ENTROPY_THRESHOLD:
            return True, f"Low entropy ({entropy} < {cls.WEAK_ENTROPY_THRESHOLD} bits)", entropy

        # Check estimate_password_strength score
        est = estimate_password_strength(password)
        if est.get("score", 0) <= 1:
            return True, f"Weak pattern: {', '.join(est.get('suggestions', []))}", entropy

        return False, "Sufficient strength", entropy

    @classmethod
    def calculate_health_score(
        cls,
        total_secrets,
        weak_count,
        reused_count,
        stale_count,
        breached_count=0,
    ):
        """
        Calculates an overall vault health score from 0 to 100.
        Penalties:
        - Breached password: -40% per occurrence in vault
        - Weak password: -25% per occurrence in vault
        - Reused password: -20% per occurrence in vault
        - Stale password: -10% per occurrence in vault
        """
        if total_secrets <= 0:
            return 100

        # Proportions of affected items
        p_breached = min(1.0, breached_count / total_secrets)
        p_weak = min(1.0, weak_count / total_secrets)
        p_reused = min(1.0, reused_count / total_secrets)
        p_stale = min(1.0, stale_count / total_secrets)

        # Weighted penalty: scaled up so vulnerabilities significantly impact the score
        penalty = (p_breached * 50.0) + (p_weak * 35.0) + (p_reused * 25.0) + (p_stale * 15.0)
        score = max(0, min(100, int(round(100.0 - penalty))))
        return score

    @classmethod
    def check_hibp_breach(cls, password, timeout=3):
        """
        Performs HaveIBeenPwned k-anonymity breach check for a single password.
        Returns: tuple (is_breached: bool, breach_count: int)
        """
        return check_password_breach(password, timeout=timeout)

    @staticmethod
    def _compute_age_days(date_val, now_utc):
        if not date_val:
            return None
        if isinstance(date_val, str):
            try:
                date_val = datetime.fromisoformat(date_val)
            except Exception:
                return None

        # Ensure timezone-aware for comparison
        if date_val.tzinfo is None:
            date_val = date_val.replace(tzinfo=timezone.utc)

        diff = now_utc - date_val
        return max(0, diff.days)
