import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from dev.abhishekraha.secretmanager.core.ReleaseUpdateService import ReleaseUpdateService


class _FakeHttpResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._payload


class ReleaseUpdateServiceTests(unittest.TestCase):
    def test_check_for_updates_marks_newer_release_and_prefers_download_url(self):
        release_payload = {
            "tag_name": "v2.0.4",
            "html_url": "https://github.com/example/releases/v2.0.4",
            "zipball_url": "https://api.github.com/repos/example/project/zipball/v2.0.4",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        service = ReleaseUpdateService(
            current_version="v2.0.3",
            cache_file="ignored-cache.json",
            stale_after_days=30,
        )

        with patch.object(service, "_save_cached_payload"):
            with patch(
                "dev.abhishekraha.secretmanager.core.ReleaseUpdateService.urlopen",
                return_value=_FakeHttpResponse(release_payload),
            ):
                status = service.check_for_updates()

        self.assertTrue(status["update_available"])
        self.assertFalse(status["is_stale"])
        self.assertEqual("v2.0.4", status["latest_version_label"])
        self.assertEqual(release_payload["zipball_url"], status["download_url"])
        self.assertEqual("update", service.get_release_indicator(status))

    def test_check_for_updates_marks_release_as_stale_after_threshold(self):
        release_payload = {
            "tag_name": "v2.0.3",
            "html_url": "https://github.com/example/releases/v2.0.3",
            "zipball_url": "https://api.github.com/repos/example/project/zipball/v2.0.3",
            "published_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
        }

        service = ReleaseUpdateService(
            current_version="v2.0.3",
            cache_file="ignored-cache.json",
            stale_after_days=30,
        )

        with patch.object(service, "_save_cached_payload"):
            with patch(
                "dev.abhishekraha.secretmanager.core.ReleaseUpdateService.urlopen",
                return_value=_FakeHttpResponse(release_payload),
            ):
                status = service.check_for_updates()

        self.assertFalse(status["update_available"])
        self.assertTrue(status["is_stale"])
        self.assertEqual("stale", service.get_release_indicator(status))

    def test_cached_release_status_is_used_when_network_fetch_fails(self):
        checked_at = datetime.now(timezone.utc).isoformat()
        cached_payload = {
            "tag_name": "v2.0.5",
            "name": "v2.0.5",
            "html_url": "https://github.com/example/releases/v2.0.5",
            "zipball_url": "https://api.github.com/repos/example/project/zipball/v2.0.5",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "checked_at": checked_at,
        }

        service = ReleaseUpdateService(
            current_version="v2.0.3",
            cache_file="ignored-cache.json",
            stale_after_days=30,
        )

        with patch.object(service, "_load_cached_payload", return_value=cached_payload):
            with patch(
                "dev.abhishekraha.secretmanager.core.ReleaseUpdateService.urlopen",
                side_effect=OSError("network unavailable"),
            ):
                status = service.check_for_updates()

        self.assertTrue(status["update_available"])
        self.assertEqual("cache-fallback", status["source"])


if __name__ == "__main__":
    unittest.main()
