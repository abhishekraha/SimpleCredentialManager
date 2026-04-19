import io
import json
import shutil
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from dev.abhishekraha.secretmanager.core.ReleaseUpdateService import (
    ReleaseUpdateError,
    ReleaseUpdateService,
)


class _FakeHttpResponse:
    def __init__(self, payload):
        if isinstance(payload, bytes):
            self._payload = payload
        else:
            self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._payload


class ReleaseUpdateServiceTests(unittest.TestCase):
    def test_check_for_updates_marks_newer_release_and_prefers_tag_archive_download_url(self):
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
        self.assertEqual(
            "https://github.com/abhishekraha/SimpleCredentialManager/archive/refs/tags/v2.0.4.zip",
            status["download_url"],
        )
        self.assertEqual("update", service.get_release_indicator(status))

    def test_check_for_updates_builds_archive_url_when_zipball_is_missing(self):
        release_payload = {
            "tag_name": "v2.0.4",
            "html_url": "https://github.com/example/releases/v2.0.4",
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

        self.assertEqual(
            "https://github.com/abhishekraha/SimpleCredentialManager/archive/refs/tags/v2.0.4.zip",
            status["download_url"],
        )

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

    def test_install_update_downloads_release_and_refreshes_dependencies(self):
        archive_bytes = _build_release_archive(
            {
                "SimpleCredentialManagerUi.py": "print('new ui')\n",
                "SimpleCredentialManagerCli.py": "print('new cli')\n",
                "requirements.txt": "cryptography==45.0.0\n",
                "dev/abhishekraha/secretmanager/__init__.py": "",
                "dev/abhishekraha/secretmanager/core/new_module.py": "NEW_VALUE = True\n",
            }
        )

        install_root = Path.cwd() / "tests" / f"_tmp_install_root_{uuid4().hex}"
        self.addCleanup(lambda: shutil.rmtree(install_root, ignore_errors=True))

        install_root.mkdir(parents=True, exist_ok=True)
        update_work_directory = install_root / ".update-temp"
        (install_root / "SimpleCredentialManagerUi.py").write_text("print('old ui')\n", encoding="utf-8")
        (install_root / "SimpleCredentialManagerCli.py").write_text("print('old cli')\n", encoding="utf-8")
        (install_root / "requirements.txt").write_text("cryptography==44.0.0\n", encoding="utf-8")
        (install_root / "dev" / "abhishekraha" / "secretmanager" / "core").mkdir(parents=True, exist_ok=True)
        (install_root / ".venv").mkdir()
        (install_root / ".venv" / "keep.txt").write_text("keep me\n", encoding="utf-8")

        service = ReleaseUpdateService(
            current_version="v2.0.7",
            cache_file=install_root / "ignored-cache.json",
            application_root=install_root,
            update_work_directory=update_work_directory,
        )
        release_status = {
            "update_available": True,
            "download_url": "https://example.com/releases/latest.zip",
            "latest_version_label": "v2.0.8",
        }

        with patch(
            "dev.abhishekraha.secretmanager.core.ReleaseUpdateService.urlopen",
            return_value=_FakeHttpResponse(archive_bytes),
        ):
            with patch(
                "dev.abhishekraha.secretmanager.core.ReleaseUpdateService.subprocess.run"
            ) as mocked_subprocess_run:
                result = service.install_update(
                    release_status=release_status,
                    target_directory=install_root,
                    python_executable="python-test",
                )

        self.assertEqual("print('new ui')\n", (install_root / "SimpleCredentialManagerUi.py").read_text(encoding="utf-8"))
        self.assertEqual("print('new cli')\n", (install_root / "SimpleCredentialManagerCli.py").read_text(encoding="utf-8"))
        self.assertEqual(
            "NEW_VALUE = True\n",
            (install_root / "dev" / "abhishekraha" / "secretmanager" / "core" / "new_module.py").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual("keep me\n", (install_root / ".venv" / "keep.txt").read_text(encoding="utf-8"))
        mocked_subprocess_run.assert_called_once_with(
            [
                "python-test",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(install_root / "requirements.txt"),
            ],
            cwd=install_root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertTrue(result["restart_required"])
        self.assertEqual("v2.0.8", result["latest_version_label"])

    def test_install_update_requires_available_release(self):
        service = ReleaseUpdateService(
            current_version="v2.0.7",
            cache_file="ignored-cache.json",
        )

        with self.assertRaises(ReleaseUpdateError):
            service.install_update(release_status={"update_available": False})


def _build_release_archive(files_by_path):
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        for relative_path, contents in files_by_path.items():
            archive.writestr(f"SimpleCredentialManager-v2.0.8/{relative_path}", contents)
    return archive_buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
