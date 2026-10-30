import os
import json
import tempfile
import unittest
from pathlib import Path

from dev.abhishekraha.secretmanager.server.DeviceRegistry import DeviceRegistry


class TestDeviceRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name) / "devices.json"
        self.registry = DeviceRegistry(storage_path=self.storage_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_enrollment_token_get_or_create_and_rotate(self):
        token1 = self.registry.get_or_create_enrollment_token()
        self.assertTrue(token1 and isinstance(token1, str))
        self.assertGreaterEqual(len(token1), 32)

        # Same token returned on subsequent call
        token2 = self.registry.get_or_create_enrollment_token()
        self.assertEqual(token1, token2)

        # Persistence: new instance with same file returns same token
        reg2 = DeviceRegistry(storage_path=self.storage_path)
        self.assertEqual(reg2.get_or_create_enrollment_token(), token1)

        # Rotate token
        token3 = self.registry.rotate_enrollment_token()
        self.assertNotEqual(token1, token3)
        self.assertEqual(self.registry.get_or_create_enrollment_token(), token3)

    def test_request_enrollment(self):
        res = self.registry.request_enrollment("MacBook Pro", client_ip="192.168.1.50")
        self.assertIn("device_id", res)
        self.assertIn("device_token", res)
        self.assertIn("fingerprint", res)
        self.assertEqual(res["status"], "PENDING")
        self.assertEqual(res["device_name"], "MacBook Pro")
        self.assertEqual(res["client_ip"], "192.168.1.50")

        # Check listed devices
        devices = self.registry.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["device_id"], res["device_id"])
        self.assertEqual(devices[0]["status"], "PENDING")
        # In list_devices, device_token is sensitive or hashed; fingerprint is present
        self.assertEqual(devices[0]["fingerprint"], res["fingerprint"])

    def test_is_device_approved_pending(self):
        res = self.registry.request_enrollment("iPhone 15")
        token = res["device_token"]
        self.assertFalse(self.registry.is_device_approved(token))

    def test_approve_device_by_id_and_fingerprint(self):
        res1 = self.registry.request_enrollment("Device 1")
        res2 = self.registry.request_enrollment("Device 2")

        # Approve device 1 by id
        success1 = self.registry.approve_device(res1["device_id"])
        self.assertTrue(success1)
        self.assertTrue(self.registry.is_device_approved(res1["device_token"]))

        # Approve device 2 by fingerprint
        success2 = self.registry.approve_device(res2["fingerprint"])
        self.assertTrue(success2)
        self.assertTrue(self.registry.is_device_approved(res2["device_token"]))

        # Check non-existent device
        self.assertFalse(self.registry.approve_device("non-existent-id"))

    def test_revoke_device(self):
        res = self.registry.request_enrollment("Work Laptop")
        token = res["device_token"]
        self.registry.approve_device(res["device_id"])
        self.assertTrue(self.registry.is_device_approved(token))

        # Revoke device
        revoked = self.registry.revoke_device(res["device_id"])
        self.assertTrue(revoked)
        self.assertFalse(self.registry.is_device_approved(token))

        # List devices shows REVOKED status
        devices = self.registry.list_devices()
        matched = [d for d in devices if d["device_id"] == res["device_id"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["status"], "REVOKED")

    def test_persistence_across_instances(self):
        res = self.registry.request_enrollment("Android Phone")
        self.registry.approve_device(res["device_id"])

        reg2 = DeviceRegistry(storage_path=self.storage_path)
        self.assertTrue(reg2.is_device_approved(res["device_token"]))
        devices = reg2.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
