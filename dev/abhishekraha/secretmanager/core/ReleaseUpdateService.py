import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    APP_CONFIG_DIR,
    APP_REPOSITORY_URL,
    APP_RELEASES_URL,
    APP_VERSION,
    RELEASE_STALE_AFTER_DAYS,
    RELEASE_STATUS_CACHE_FILE,
    RELEASE_UPDATE_API_URL,
    RELEASE_UPDATE_REQUEST_TIMEOUT_SECONDS,
)


class ReleaseUpdateError(RuntimeError):
    pass


class ReleaseUpdateService:
    def __init__(
        self,
        current_version=APP_VERSION,
        api_url=RELEASE_UPDATE_API_URL,
        release_page_url=APP_RELEASES_URL,
        cache_file=RELEASE_STATUS_CACHE_FILE,
        stale_after_days=RELEASE_STALE_AFTER_DAYS,
        request_timeout_seconds=RELEASE_UPDATE_REQUEST_TIMEOUT_SECONDS,
        application_root=None,
        update_work_directory=None,
    ):
        self._current_version = current_version
        self._api_url = api_url
        self._release_page_url = release_page_url
        self._cache_file = Path(cache_file)
        self._stale_after_days = stale_after_days
        self._request_timeout_seconds = request_timeout_seconds
        self._application_root = (
            Path(application_root)
            if application_root is not None
            else Path(__file__).resolve().parents[4]
        )
        self._update_work_directory = (
            Path(update_work_directory)
            if update_work_directory is not None
            else Path(APP_CONFIG_DIR) / "updates"
        )

    def check_for_updates(self):

        fetched_payload = self._fetch_latest_release_payload()
        if fetched_payload:
            self._save_cached_payload(fetched_payload)
            return self._build_status(fetched_payload, source="network")

        cached_payload = self._load_cached_payload()
        if cached_payload:
            return self._build_status(cached_payload, source="cache-fallback")
        return self._build_status({}, source="unavailable")

    def get_release_indicator(self, release_status):
        if release_status.get("update_available"):
            return "update"
        if release_status.get("is_stale"):
            return "stale"
        return "normal"

    def build_cli_warning_lines(self, release_status):
        lines = []
        latest_version = release_status.get("latest_version_label") or "unknown"

        if release_status.get("update_available"):
            lines.append(f"[WARNING] A newer version is available on GitHub: {latest_version}")
            lines.append(f"[WARNING] Download: {release_status.get('download_url') or release_status.get('release_url')}")
        elif release_status.get("is_stale"):
            lines.append(
                "[WARNING] The most recent GitHub release is older than "
                f"{self._stale_after_days} days."
            )
            lines.append(f"[WARNING] Latest release: {latest_version}")

        return lines

    def install_update(self, release_status=None, target_directory=None, python_executable=None):
        release_status = release_status or self.check_for_updates()
        if not release_status.get("update_available"):
            raise ReleaseUpdateError("No update is currently available.")

        install_root = Path(target_directory) if target_directory is not None else self._application_root
        self._validate_install_root(install_root)

        download_url = release_status.get("download_url")
        if not download_url:
            raise ReleaseUpdateError("The latest release did not include a downloadable archive.")

        latest_version = release_status.get("latest_version_label") or "the latest version"
        python_command = python_executable or sys.executable

        self._update_work_directory.mkdir(parents=True, exist_ok=True)
        temp_root = self._update_work_directory / f"simple-credential-manager-update-{uuid4().hex}"
        try:
            temp_root.mkdir(parents=True, exist_ok=False)
            archive_path = temp_root / "release.zip"
            extracted_path = temp_root / "release"
            self._download_release_archive(download_url, archive_path)
            release_root = self._extract_release_archive(archive_path, extracted_path)
            self._copy_release_contents(release_root, install_root)
            self._install_requirements(install_root, python_command)
        except ReleaseUpdateError:
            raise
        except (OSError, subprocess.SubprocessError, ValueError, zipfile.BadZipFile) as exc:
            raise ReleaseUpdateError(f"Automatic upgrade failed: {exc}") from exc
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        return {
            "latest_version_label": latest_version,
            "restart_required": True,
            "target_directory": str(install_root),
        }

    def _fetch_latest_release_payload(self):
        request = Request(
            self._api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"SimpleCredentialManager/{self._current_version}",
            },
        )
        try:
            with urlopen(request, timeout=self._request_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None

    def _build_status(self, payload, source):
        tag_name = payload.get("tag_name") or payload.get("name") or ""
        latest_version = _normalize_version(tag_name)
        current_version = _normalize_version(self._current_version)
        published_at = payload.get("published_at") or payload.get("created_at") or ""
        days_since_release = _days_since_release(published_at)
        archive_download_url = _build_archive_download_url(tag_name)

        return {
            "current_version": current_version,
            "current_version_label": _to_version_label(current_version),
            "latest_version": latest_version,
            "latest_version_label": _to_version_label(latest_version) if latest_version else "",
            "release_url": payload.get("html_url") or self._release_page_url,
            "download_url": archive_download_url or payload.get("zipball_url") or payload.get("html_url") or self._release_page_url,
            "published_at": published_at,
            "days_since_release": days_since_release,
            "update_available": bool(latest_version and _compare_versions(latest_version, current_version) > 0),
            "is_stale": days_since_release is not None and days_since_release > self._stale_after_days,
            "source": source,
        }

    def _load_cached_payload(self):
        if not self._cache_file.exists():
            return None
        try:
            return json.loads(self._cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _save_cached_payload(self, payload):
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            cached_payload = {
                "tag_name": payload.get("tag_name") or payload.get("name") or "",
                "name": payload.get("name") or payload.get("tag_name") or "",
                "html_url": payload.get("html_url") or self._release_page_url,
                "zipball_url": payload.get("zipball_url") or "",
                "published_at": payload.get("published_at") or payload.get("created_at") or "",
                "created_at": payload.get("created_at") or payload.get("published_at") or "",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            self._cache_file.write_text(json.dumps(cached_payload), encoding="utf-8")
        except OSError:
            return

    def _validate_install_root(self, install_root):
        install_root = Path(install_root)
        required_paths = [
            install_root / "SimpleCredentialManagerUi.py",
            install_root / "SimpleCredentialManagerCli.py",
            install_root / "requirements.txt",
            install_root / "dev",
        ]
        if not install_root.exists() or not all(path.exists() for path in required_paths):
            raise ReleaseUpdateError(
                f"Automatic upgrade can only run from a Simple Credential Manager install folder: {install_root}"
            )

    def _download_release_archive(self, download_url, destination):
        request_headers = {
            "User-Agent": f"SimpleCredentialManager/{self._current_version}",
        }
        if _is_github_archive_api_url(download_url):
            request_headers["Accept"] = "application/vnd.github+json"
        request = Request(
            download_url,
            headers=request_headers,
        )
        try:
            with urlopen(request, timeout=self._request_timeout_seconds) as response:
                destination.write_bytes(response.read())
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ReleaseUpdateError(f"Could not download the latest release archive: {exc}") from exc

    def _extract_release_archive(self, archive_path, destination):
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(destination)

        release_root = self._find_release_root(destination)
        if release_root is None:
            raise ReleaseUpdateError("The downloaded archive does not contain a valid application bundle.")
        return release_root

    def _find_release_root(self, extracted_root):
        for candidate in extracted_root.rglob("SimpleCredentialManagerUi.py"):
            potential_root = candidate.parent
            if _looks_like_install_root(potential_root):
                return potential_root
        return None

    def _copy_release_contents(self, source_root, install_root):
        ignored_directory_names = {".git", ".venv", "venv", "__pycache__", ".idea"}
        ignored_file_suffixes = {".pyc", ".pyo"}

        for current_root, directory_names, file_names in os.walk(source_root):
            current_root_path = Path(current_root)
            relative_root = current_root_path.relative_to(source_root)
            directory_names[:] = [name for name in directory_names if name not in ignored_directory_names]

            target_root = install_root if relative_root == Path(".") else install_root / relative_root
            if target_root.exists() and not target_root.is_dir():
                target_root.unlink()
            target_root.mkdir(parents=True, exist_ok=True)

            for file_name in file_names:
                if Path(file_name).suffix in ignored_file_suffixes:
                    continue
                source_path = current_root_path / file_name
                target_path = target_root / file_name
                if target_path.exists() and target_path.is_dir():
                    shutil.rmtree(target_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)

    def _install_requirements(self, install_root, python_command):
        requirements_file = install_root / "requirements.txt"
        if not requirements_file.exists():
            return
        try:
            subprocess.run(
                [
                    python_command,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-r",
                    str(requirements_file),
                ],
                cwd=install_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise ReleaseUpdateError(f"Could not refresh dependencies after upgrading: {exc}") from exc
        except subprocess.CalledProcessError as exc:
            command_output = (exc.stderr or exc.stdout or "").strip()
            detail = command_output.splitlines()[-1] if command_output else "pip install exited with an error."
            raise ReleaseUpdateError(f"Could not refresh dependencies after upgrading: {detail}") from exc


def _normalize_version(version_value):
    version_text = str(version_value or "").strip()
    if version_text.lower().startswith("v"):
        version_text = version_text[1:]
    return version_text


def _to_version_label(version_value):
    normalized = _normalize_version(version_value)
    if not normalized:
        return ""
    return f"v{normalized}"


def _compare_versions(left_version, right_version):
    left_tuple = _version_tuple(left_version)
    right_tuple = _version_tuple(right_version)
    max_length = max(len(left_tuple), len(right_tuple))
    left_tuple += (0,) * (max_length - len(left_tuple))
    right_tuple += (0,) * (max_length - len(right_tuple))
    if left_tuple > right_tuple:
        return 1
    if left_tuple < right_tuple:
        return -1
    return 0


def _version_tuple(version_value):
    digits = re.findall(r"\d+", _normalize_version(version_value))
    return tuple(int(value) for value in digits) if digits else (0,)


def _days_since_release(release_timestamp):
    parsed_timestamp = _parse_iso_datetime(release_timestamp)
    if parsed_timestamp is None:
        return None
    return (datetime.now(timezone.utc) - parsed_timestamp).days


def _parse_iso_datetime(timestamp_value):
    if not timestamp_value:
        return None
    normalized = str(timestamp_value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _build_archive_download_url(tag_name):
    normalized_tag = str(tag_name or "").strip()
    if not normalized_tag:
        return ""
    return f"{APP_REPOSITORY_URL}/archive/refs/tags/{normalized_tag}.zip"


def _looks_like_install_root(candidate):
    candidate = Path(candidate)
    return (
        (candidate / "SimpleCredentialManagerUi.py").exists()
        and (candidate / "SimpleCredentialManagerCli.py").exists()
        and (candidate / "requirements.txt").exists()
        and (candidate / "dev").exists()
    )


def _is_github_archive_api_url(download_url):
    normalized_url = str(download_url or "")
    return normalized_url.startswith("https://api.github.com/repos/") and "/zipball/" in normalized_url
