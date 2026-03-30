import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    APP_RELEASES_URL,
    APP_VERSION,
    RELEASE_STALE_AFTER_DAYS,
    RELEASE_STATUS_CACHE_FILE,
    RELEASE_UPDATE_API_URL,
    RELEASE_UPDATE_REQUEST_TIMEOUT_SECONDS,
)


class ReleaseUpdateService:
    def __init__(
        self,
        current_version=APP_VERSION,
        api_url=RELEASE_UPDATE_API_URL,
        release_page_url=APP_RELEASES_URL,
        cache_file=RELEASE_STATUS_CACHE_FILE,
        stale_after_days=RELEASE_STALE_AFTER_DAYS,
        request_timeout_seconds=RELEASE_UPDATE_REQUEST_TIMEOUT_SECONDS,
    ):
        self._current_version = current_version
        self._api_url = api_url
        self._release_page_url = release_page_url
        self._cache_file = Path(cache_file)
        self._stale_after_days = stale_after_days
        self._request_timeout_seconds = request_timeout_seconds

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
        latest_version = _normalize_version(payload.get("tag_name") or payload.get("name") or "")
        current_version = _normalize_version(self._current_version)
        published_at = payload.get("published_at") or payload.get("created_at") or ""
        days_since_release = _days_since_release(published_at)

        return {
            "current_version": current_version,
            "current_version_label": _to_version_label(current_version),
            "latest_version": latest_version,
            "latest_version_label": _to_version_label(latest_version) if latest_version else "",
            "release_url": payload.get("html_url") or self._release_page_url,
            "download_url": payload.get("zipball_url") or payload.get("html_url") or self._release_page_url,
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
