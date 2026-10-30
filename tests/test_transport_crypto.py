import base64
import json
import unittest

from dev.abhishekraha.secretmanager.server.TransportCrypto import (
    derive_transport_key,
    encrypt_payload,
    decrypt_payload,
)


class TestTransportCrypto(unittest.TestCase):
    def setUp(self):
        self.device_token = "test-device-token-123456"

    def test_derive_transport_key_deterministic_and_length(self):
        key1 = derive_transport_key(self.device_token)
        key2 = derive_transport_key(self.device_token)
        self.assertIsInstance(key1, bytes)
        self.assertEqual(len(key1), 32)
        self.assertEqual(key1, key2)

        other_key = derive_transport_key("different-token")
        self.assertNotEqual(key1, other_key)

    def test_derive_transport_key_requires_string(self):
        with self.assertRaises(ValueError):
            derive_transport_key("")
        with self.assertRaises(TypeError):
            derive_transport_key(None)

    def test_encrypt_payload_structure(self):
        data = {"hello": "world", "num": 42}
        encrypted = encrypt_payload(data, self.device_token)
        self.assertIsInstance(encrypted, dict)
        self.assertIn("iv", encrypted)
        self.assertIn("ciphertext", encrypted)

        # Ensure iv and ciphertext are valid base64
        iv_bytes = base64.b64decode(encrypted["iv"])
        self.assertEqual(len(iv_bytes), 12)  # 12-byte standard GCM nonce
        ct_bytes = base64.b64decode(encrypted["ciphertext"])
        self.assertTrue(len(ct_bytes) > 16)  # payload + 16-byte tag

    def test_roundtrip_dict_payload(self):
        original = {"password": "SuperSecretPassword123!", "tags": ["admin", "login"]}
        encrypted = encrypt_payload(original, self.device_token)
        decrypted = decrypt_payload(encrypted, self.device_token)
        self.assertEqual(decrypted, original)

    def test_roundtrip_str_payload(self):
        original = "Just a raw string payload"
        encrypted = encrypt_payload(original, self.device_token)
        decrypted = decrypt_payload(encrypted, self.device_token)
        self.assertEqual(decrypted, original)

    def test_decrypt_with_wrong_device_token_fails(self):
        original = {"secret": "data"}
        encrypted = encrypt_payload(original, self.device_token)
        with self.assertRaises(Exception):
            decrypt_payload(encrypted, "wrong-device-token")

    def test_decrypt_corrupted_ciphertext_fails(self):
        original = {"secret": "data"}
        encrypted = encrypt_payload(original, self.device_token)
        ct_bytes = bytearray(base64.b64decode(encrypted["ciphertext"]))
        ct_bytes[0] ^= 0xFF  # tamper byte
        corrupted_encrypted = {
            "iv": encrypted["iv"],
            "ciphertext": base64.b64encode(ct_bytes).decode("ascii"),
        }
        with self.assertRaises(Exception):
            decrypt_payload(corrupted_encrypted, self.device_token)

    def test_decrypt_corrupted_iv_fails(self):
        original = {"secret": "data"}
        encrypted = encrypt_payload(original, self.device_token)
        iv_bytes = bytearray(base64.b64decode(encrypted["iv"]))
        iv_bytes[0] ^= 0xFF
        corrupted_encrypted = {
            "iv": base64.b64encode(iv_bytes).decode("ascii"),
            "ciphertext": encrypted["ciphertext"],
        }
        with self.assertRaises(Exception):
            decrypt_payload(corrupted_encrypted, self.device_token)

    def test_decrypt_invalid_payload_dict(self):
        with self.assertRaises(ValueError):
            decrypt_payload({"only_iv": "abc"}, self.device_token)
        with self.assertRaises(ValueError):
            decrypt_payload("not-a-dict", self.device_token)


if __name__ == "__main__":
    unittest.main()
