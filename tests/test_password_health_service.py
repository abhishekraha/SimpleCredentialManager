import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from dev.abhishekraha.secretmanager.core.PasswordHealthService import PasswordHealthService
from dev.abhishekraha.secretmanager.model.Secret import Secret


class PasswordHealthServiceTests(unittest.TestCase):
    def test_empty_vault_audit(self):
        result = PasswordHealthService.audit_vault([])
        self.assertEqual(100, result["health_score"])
        self.assertEqual(0, result["total_secrets"])
        self.assertEqual([], result["weak_secrets"])
        self.assertEqual([], result["reused_secrets"])
        self.assertEqual([], result["stale_secrets"])

    def test_weak_password_detection(self):
        # Short password
        is_weak, reason, _ = PasswordHealthService.is_weak_password("short")
        self.assertTrue(is_weak)
        self.assertIn("Too short", reason)

        # Low entropy simple password
        is_weak, reason, _ = PasswordHealthService.is_weak_password("123456789012")
        self.assertTrue(is_weak)

        # Strong high-entropy password
        is_weak, reason, _ = PasswordHealthService.is_weak_password("K8#mP$9vL!2zQx@4wR&t")
        self.assertFalse(is_weak)

    def test_reused_passwords_detection(self):
        secrets = [
            Secret("service1", "user1", "shared_p@ssw0rd123!"),
            Secret("service2", "user2", "shared_p@ssw0rd123!"),
            Secret("service3", "user3", "unique_long_p@ssw0rd_987!"),
        ]
        result = PasswordHealthService.audit_vault(secrets)
        self.assertEqual(3, result["total_secrets"])
        self.assertEqual(1, len(result["reused_secrets"]))
        self.assertEqual(2, result["reused_secrets"][0]["count"])
        self.assertEqual(["service1", "service2"], result["reused_secrets"][0]["secret_names"])

    def test_stale_passwords_detection(self):
        old_time = datetime.now(timezone.utc) - timedelta(days=400)
        recent_time = datetime.now(timezone.utc) - timedelta(days=30)

        secrets = [
            Secret("stale_item", "user", "K8#mP$9vL!2zQx@4wR&t", create_date=old_time),
            Secret("fresh_item", "user", "K8#mP$9vL!2zQx@4wR&t", create_date=recent_time),
        ]
        result = PasswordHealthService.audit_vault(secrets)
        self.assertEqual(1, len(result["stale_secrets"]))
        self.assertEqual("stale_item", result["stale_secrets"][0]["name"])
        self.assertGreaterEqual(result["stale_secrets"][0]["age_days"], 399)

    def test_hibp_k_anonymity_breach_check(self):
        with patch(
            "dev.abhishekraha.secretmanager.core.PasswordHealthService.check_password_breach"
        ) as mock_breach:
            mock_breach.return_value = (True, 1500)

            secrets = [
                Secret("breached_item", "user", "P@ssword123456789!"),
            ]
            result = PasswordHealthService.audit_vault(secrets, check_breaches=True)

            self.assertEqual(1, len(result["breached_secrets"]))
            self.assertEqual("breached_item", result["breached_secrets"][0]["name"])
            self.assertEqual(1500, result["breached_secrets"][0]["breach_count"])
            mock_breach.assert_called_once_with("P@ssword123456789!", timeout=3)

    def test_calculate_health_score(self):
        # Perfect vault
        perfect = PasswordHealthService.calculate_health_score(
            total_secrets=10, weak_count=0, reused_count=0, stale_count=0, breached_count=0
        )
        self.assertEqual(100, perfect)

        # Compromised vault
        poor = PasswordHealthService.calculate_health_score(
            total_secrets=10, weak_count=5, reused_count=5, stale_count=5, breached_count=2
        )
        self.assertLess(poor, 60)


if __name__ == "__main__":
    unittest.main()
