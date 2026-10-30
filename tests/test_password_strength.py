import unittest
from unittest.mock import MagicMock, patch

from dev.abhishekraha.secretmanager.utils.BreachChecker import check_password_breach
from dev.abhishekraha.secretmanager.utils.PasswordStrengthUtils import (
    calculate_entropy,
    estimate_password_strength,
    has_sequential_chars,
    validate_master_password_policy,
)


class PasswordStrengthTests(unittest.TestCase):
    def test_calculate_entropy_empty_and_simple(self):
        self.assertEqual(calculate_entropy(""), 0.0)
        entropy_digits = calculate_entropy("12345678")
        self.assertGreater(entropy_digits, 0.0)
        entropy_complex = calculate_entropy("T3$t!P@ssw0rd#2026")
        self.assertGreater(entropy_complex, entropy_digits)

    def test_has_sequential_chars(self):
        self.assertTrue(has_sequential_chars("my1234pass"))
        self.assertTrue(has_sequential_chars("abcde_user"))
        self.assertTrue(has_sequential_chars("4321_reverse"))
        self.assertFalse(has_sequential_chars("x9k!p2z#"))

    def test_estimate_password_strength(self):
        weak = estimate_password_strength("123456")
        self.assertEqual(weak["score"], 0)
        self.assertEqual(weak["label"], "Very Weak")
        self.assertTrue(len(weak["suggestions"]) > 0)

        strong = estimate_password_strength("C0rrect-H0rse-Batt3ry-Staple!")
        self.assertIn(strong["score"], (3, 4))
        self.assertIn(strong["label"], ("Strong", "Very Strong"))

    def test_validate_master_password_policy(self):
        # Empty
        valid, err = validate_master_password_policy("")
        self.assertFalse(valid)
        self.assertIn("cannot be empty", err)

        # Too short
        valid, err = validate_master_password_policy("short", min_length=8)
        self.assertFalse(valid)
        self.assertIn("at least 8 characters", err)

        # Repetitive characters
        valid, err = validate_master_password_policy("aaaaaaaaa")
        self.assertFalse(valid)

        # Strong valid password
        valid, err = validate_master_password_policy("MySecureMasterPassw0rd#2026!")
        self.assertTrue(valid)
        self.assertIsNone(err)

    @patch("dev.abhishekraha.secretmanager.utils.BreachChecker.urllib.request.urlopen")
    def test_check_password_breach_detected(self, mock_urlopen):
        # Mock API returning suffix match
        mock_response = MagicMock()
        mock_response.status = 200
        # SHA-1 of 'password' is 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
        # prefix: 5BAA6, suffix: 1E4C9B93F3F0682250B6CF8331B7EE68FD8
        mock_response.read.return_value = (
            b"0018A45C4D6379A679A4:1\n1E4C9B93F3F0682250B6CF8331B7EE68FD8:3861493\n"
        )
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        is_breached, count = check_password_breach("password")
        self.assertTrue(is_breached)
        self.assertEqual(count, 3861493)

    @patch("dev.abhishekraha.secretmanager.utils.BreachChecker.urllib.request.urlopen")
    def test_check_password_breach_not_detected(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"0018A45C4D6379A679A4:1\nFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:2\n"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        is_breached, count = check_password_breach("password")
        self.assertFalse(is_breached)
        self.assertEqual(count, 0)

    @patch("dev.abhishekraha.secretmanager.utils.BreachChecker.urllib.request.urlopen", side_effect=Exception("Network down"))
    def test_check_password_breach_network_error_graceful_handling(self, mock_urlopen):
        is_breached, count = check_password_breach("password")
        self.assertFalse(is_breached)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
