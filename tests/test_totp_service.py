import unittest

from dev.abhishekraha.secretmanager.core.TotpService import TotpService


class TotpServiceTests(unittest.TestCase):
    # RFC 6238 Appendix B test vector key for SHA1 (Ascii "12345678901234567890" in Base32)
    # 12345678901234567890 in base32 is GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ
    RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

    def test_rfc6238_test_vectors(self):
        # Time = 59s: TOTP = 287082
        res_59 = TotpService.generate_totp(self.RFC_SECRET, timestamp=59)
        self.assertEqual("287082", res_59["code"])
        self.assertEqual("287 082", res_59["formatted_code"])
        self.assertEqual(1, res_59["remaining_seconds"])

        # Time = 1111111109s: TOTP = 081804
        res_1111111109 = TotpService.generate_totp(self.RFC_SECRET, timestamp=1111111109)
        self.assertEqual("081804", res_1111111109["code"])
        self.assertEqual("081 804", res_1111111109["formatted_code"])

        # Time = 1234567890s: TOTP = 005924
        res_1234567890 = TotpService.generate_totp(self.RFC_SECRET, timestamp=1234567890)
        self.assertEqual("005924", res_1234567890["code"])

    def test_parse_raw_base32_and_cleaning(self):
        # Test spaces and lowercase
        clean = TotpService.parse_secret(" gez dgn bvgy 3tqojq gez dgn bvgy 3tqojq ")
        self.assertEqual(self.RFC_SECRET, clean)

        # Hyphens
        clean_hyphen = TotpService.parse_secret("GEZD-GNBV-GY3T-QOJQ")
        self.assertEqual("GEZDGNBVGY3TQOJQ", clean_hyphen)

    def test_parse_otpauth_uri(self):
        uri = (
            "otpauth://totp/GitHub:alice@example.com?"
            "secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=GitHub&algorithm=SHA1&digits=6&period=30"
        )
        clean = TotpService.parse_secret(uri)
        self.assertEqual(self.RFC_SECRET, clean)

        metadata = TotpService.parse_uri_metadata(uri)
        self.assertIsNotNone(metadata)
        self.assertEqual("GitHub:alice@example.com", metadata["label"])
        self.assertEqual("GitHub", metadata["issuer"])
        self.assertEqual(6, metadata["digits"])
        self.assertEqual(30, metadata["period"])

        # Generate from URI directly
        res = TotpService.generate_totp(uri, timestamp=59)
        self.assertEqual("287082", res["code"])

    def test_remaining_seconds_and_progress(self):
        # Timestamp 30 -> remaining = 30, progress = 0.0
        rem_30 = TotpService.get_remaining_seconds(30)
        self.assertEqual(30, rem_30)

        # Timestamp 45 -> remaining = 15
        rem_45 = TotpService.get_remaining_seconds(45)
        self.assertEqual(15, rem_45)

        res = TotpService.generate_totp(self.RFC_SECRET, timestamp=45)
        self.assertEqual(15, res["remaining_seconds"])
        self.assertEqual(0.5, res["progress"])

    def test_verify_totp(self):
        current_res = TotpService.generate_totp(self.RFC_SECRET)
        self.assertTrue(TotpService.verify_totp(self.RFC_SECRET, current_res["code"]))
        self.assertTrue(TotpService.verify_totp(self.RFC_SECRET, current_res["formatted_code"]))
        self.assertFalse(TotpService.verify_totp(self.RFC_SECRET, "000000"))

    def test_invalid_secrets(self):
        with self.assertRaises(ValueError):
            TotpService.parse_secret("INVALID_CHARACTERS!@#$")

        with self.assertRaises(ValueError):
            TotpService.generate_totp("")


if __name__ == "__main__":
    unittest.main()
