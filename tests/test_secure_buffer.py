import unittest
from dev.abhishekraha.secretmanager.utils.SecureBuffer import SecureBuffer, zero_buffer


class SecureBufferTests(unittest.TestCase):
    def test_buffer_creation_and_reading(self):
        with SecureBuffer(b"super_secret_payload") as sb:
            self.assertEqual(sb.raw, b"super_secret_payload")
            self.assertEqual(sb.to_bytes(), b"super_secret_payload")
            self.assertEqual(len(sb), 20)
            self.assertFalse(sb.is_cleared())
            self.assertEqual(sb[0], ord(b"s"))

    def test_buffer_string_initialization(self):
        sb = SecureBuffer("secret_password_string")
        self.assertEqual(sb.raw, b"secret_password_string")
        sb.zero()
        self.assertTrue(sb.is_cleared())
        with self.assertRaises(ValueError):
            _ = sb.raw

    def test_zeroing_modifies_underlying_bytearray(self):
        underlying = bytearray(b"unmasked_secret_key_material")
        zero_buffer(underlying)
        # All bytes in underlying must now be 0
        self.assertEqual(underlying, bytearray(len(underlying)))

    def test_context_manager_clears_on_exit(self):
        sb = SecureBuffer(b"transient_data")
        with sb:
            self.assertFalse(sb.is_cleared())
            _ = sb[0]
        self.assertTrue(sb.is_cleared())
        with self.assertRaises(ValueError):
            _ = sb.buffer

    def test_empty_buffer_zeroing(self):
        # Should not raise exception
        zero_buffer(bytearray())
        zero_buffer(None)
        sb = SecureBuffer(b"")
        sb.zero()
        self.assertTrue(sb.is_cleared())


if __name__ == "__main__":
    unittest.main()
