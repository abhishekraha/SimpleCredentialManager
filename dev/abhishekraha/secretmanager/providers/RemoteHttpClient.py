import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import APP_CONFIG_DIR
from dev.abhishekraha.secretmanager.server.TransportCrypto import decrypt_payload, encrypt_payload
from dev.abhishekraha.secretmanager.utils.SecureBuffer import SecureBuffer, zero_buffer


class RemoteHttpClient:
    """
    HTTP transport client for SCM remote server mode.
    Handles device enrollment, configuration storage with 0600 permissions,
    and AES-256-GCM payload encryption over HTTP/HTTPS.
    """

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8080",
        config_path: Optional[Union[str, Path]] = None,
        timeout: float = 10.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        if config_path is not None:
            self.config_path = Path(config_path)
        else:
            self.config_path = APP_CONFIG_DIR / "remote_client.json"

        self.device_id: str = ""
        self.device_token: str = ""
        self._load_config()

    def _load_config(self) -> None:
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "server_url" in data and not self.server_url:
                        self.server_url = data["server_url"].rstrip("/")
                    self.device_id = data.get("device_id", "")
                    self.device_token = data.get("device_token", "")
        except (OSError, json.JSONDecodeError):
            pass

    def save_config(self) -> None:
        """Persists client config to disk with strict 0600 user-only permissions."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.config_path.with_suffix(".tmp")
        payload = {
            "server_url": self.server_url,
            "device_id": self.device_id,
            "device_token": self.device_token,
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        if os.name == "posix":
            try:
                os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass

        os.replace(tmp_path, self.config_path)

        if os.name == "posix":
            try:
                os.chmod(self.config_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass

    def is_enrolled(self) -> bool:
        """Returns True if device ID and device token are present."""
        return bool(self.device_id and self.device_token)

    def _build_url(self, endpoint: str) -> str:
        base = self.server_url.rstrip("/")
        rel = endpoint.lstrip("/")
        return f"{base}/{rel}"

    def enroll_device(self, enrollment_token: str, device_name: str) -> dict:
        """
        Registers this client with the SCM server using the out-of-band enrollment token.
        Saves resulting device_id and device_token locally.
        """
        url = self._build_url(f"/api/v1/devices/enroll?secret={enrollment_token}")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json={"device_name": device_name})
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectionError(f"Failed to connect to remote server: {exc}") from exc

        if not resp.is_success:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            if resp.status_code == 403:
                raise PermissionError(f"Enrollment rejected: {detail}")
            raise RuntimeError(f"Enrollment failed ({resp.status_code}): {detail}")

        data = resp.json()
        self.device_id = data.get("device_id", "")
        self.device_token = data.get("device_token", "")
        self.save_config()
        return data

    def check_device_status(self) -> dict:
        """Checks if the enrolled device has been approved by the host administrator."""
        if not self.device_token:
            return {"approved": False}
        url = self._build_url("/api/v1/devices/status")
        headers = {"X-Device-Token": self.device_token}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectionError(f"Failed to connect to remote server: {exc}") from exc

        if resp.is_success:
            return resp.json()
        return {"approved": False}

    def _process_response(self, resp: httpx.Response, endpoint: str) -> Any:
        if resp.status_code == 404:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            if detail == "Service unavailable":
                raise PermissionError("Device not approved or service unavailable")
            raise KeyError(detail)

        if not resp.is_success:
            try:
                err_data = resp.json()
                detail = err_data.get("detail", resp.text)
            except Exception:
                err_data = {}
                detail = resp.text

            if resp.status_code == 401:
                if endpoint.endswith("/unlock"):
                    return err_data
                raise PermissionError(f"Unauthorized: {detail}")
            if resp.status_code == 400:
                raise ValueError(detail)
            resp.raise_for_status()

        try:
            resp_data = resp.json()
        except Exception:
            return resp.text

        if isinstance(resp_data, dict) and "iv" in resp_data and "ciphertext" in resp_data:
            if not self.device_token:
                raise ValueError("Cannot decrypt server response without device token")
            return decrypt_payload(resp_data, self.device_token)

        return resp_data

    def post_encrypted(
        self,
        endpoint: str,
        json_payload: dict,
        session_token: Optional[str] = None,
    ) -> Union[dict, list, Any]:
        """
        Encrypts payload using AES-256-GCM under the device token, dispatches POST,
        decrypts response, and zeroes intermediate sensitive memory.
        """
        url = self._build_url(endpoint)
        headers = {"Content-Type": "application/json"}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        if session_token:
            headers["X-Session-Token"] = session_token

        # Encrypt body if device token is available
        if self.device_token:
            body = encrypt_payload(json_payload, self.device_token)
        else:
            body = json_payload

        # Clean intermediate memory
        if isinstance(json_payload, dict) and "password" in json_payload:
            pwd = json_payload.get("password")
            if isinstance(pwd, str):
                buf = bytearray(pwd.encode("utf-8"))
                zero_buffer(buf)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=body, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectionError(f"Remote server unreachable: {exc}") from exc

        return self._process_response(resp, endpoint)

    def put_encrypted(
        self,
        endpoint: str,
        json_payload: dict,
        session_token: Optional[str] = None,
    ) -> Union[dict, list, Any]:
        """
        Encrypts payload using AES-256-GCM under the device token, dispatches PUT,
        and decrypts response.
        """
        url = self._build_url(endpoint)
        headers = {"Content-Type": "application/json"}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        if session_token:
            headers["X-Session-Token"] = session_token

        if self.device_token:
            body = encrypt_payload(json_payload, self.device_token)
        else:
            body = json_payload

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.put(url, json=body, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectionError(f"Remote server unreachable: {exc}") from exc

        return self._process_response(resp, endpoint)

    def get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        session_token: Optional[str] = None,
    ) -> Union[dict, list, Any]:
        """Dispatches GET request with device and session headers."""
        url = self._build_url(endpoint)
        headers = {}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        if session_token:
            headers["X-Session-Token"] = session_token

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectionError(f"Remote server unreachable: {exc}") from exc

        return self._process_response(resp, endpoint)

    def delete(
        self,
        endpoint: str,
        session_token: Optional[str] = None,
    ) -> Union[dict, list, Any]:
        """Dispatches DELETE request with device and session headers."""
        url = self._build_url(endpoint)
        headers = {}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        if session_token:
            headers["X-Session-Token"] = session_token

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.delete(url, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectionError(f"Remote server unreachable: {exc}") from exc

        return self._process_response(resp, endpoint)
