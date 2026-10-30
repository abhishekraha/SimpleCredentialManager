import json
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field

from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.core.TotpService import TotpService
from dev.abhishekraha.secretmanager.model.Secret import Secret
from dev.abhishekraha.secretmanager.server.DeviceRegistry import DeviceRegistry
from dev.abhishekraha.secretmanager.server.SessionManager import ServerSessionManager
from dev.abhishekraha.secretmanager.server.TransportCrypto import decrypt_payload


# Pydantic Request Models
class DeviceEnrollRequest(BaseModel):
    device_name: str = Field(..., min_length=1)


class AuthUnlockRequest(BaseModel):
    password: str = Field(..., min_length=1)


class SecretCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    username: str = ""
    password: str = ""
    url: str = ""
    comments: str = ""
    category: str = "login"
    is_favorite: bool = False
    totp_secret: Optional[str] = None
    tags: Optional[List[str]] = None


class SecretUpdateRequest(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    url: Optional[str] = None
    comments: Optional[str] = None
    category: Optional[str] = None
    is_favorite: Optional[bool] = None
    totp_secret: Optional[str] = None
    tags: Optional[List[str]] = None


def create_app(
    service: Optional[SecretManagerService] = None,
    registry: Optional[DeviceRegistry] = None,
    session_manager: Optional[ServerSessionManager] = None,
    prefix: str = "",
) -> FastAPI:
    """
    Factory function creating the FastAPI application for SCM Server Mode.
    Configures device gatekeeper middleware, session validation, enrollment,
    auth, and secret CRUD endpoints.
    """
    svc = service if service is not None else SecretManagerService("scm-server")
    reg = registry if registry is not None else DeviceRegistry()
    sess_mgr = session_manager if session_manager is not None else ServerSessionManager(service=svc)

    # Initialize service
    try:
        svc.initialize()
    except Exception:
        pass

    normalized_prefix = prefix.rstrip("/") if prefix else ""

    fastapi_kwargs = {
        "title": "Simple Credential Manager Server",
        "version": "1.0.0",
    }
    if normalized_prefix:
        fastapi_kwargs["root_path"] = normalized_prefix

    app = FastAPI(**fastapi_kwargs)

    api_router = APIRouter()

    # Helper dependency for session check
    def require_session(
        request: Request,
        x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    ) -> str:
        # Check cookie first, then header, then Authorization Bearer
        token = request.cookies.get("scm_session") or x_session_token
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()

        if not token or not sess_mgr.validate_session(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: active session required",
            )
        if not svc.is_unlocked():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Vault is locked",
            )
        return token

    # Helper dependency to resolve device id from X-Device-Token
    def get_current_device_id(
        x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    ) -> str:
        return x_device_token or "unknown"

    # Enrollment Endpoints
    @api_router.post("/api/v1/devices/enroll", status_code=status.HTTP_202_ACCEPTED)
    def enroll_device(
        payload: DeviceEnrollRequest,
        request: Request,
        secret: str = Query(...),
    ):
        if not svc.is_initialized():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vault is not initialized. Please set up the master password on the server first.",
            )
        expected_secret = reg.get_or_create_enrollment_token()
        if not secret or secret != expected_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing enrollment secret",
            )
        client_ip = request.client.host if request.client else ""
        enrollment_result = reg.request_enrollment(payload.device_name, client_ip=client_ip)
        return enrollment_result

    @api_router.get("/api/v1/devices/status")
    def get_device_status(
        x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    ):
        if not x_device_token:
            return {"approved": False}
        return {"approved": reg.is_device_approved(x_device_token)}

    # Auth Endpoints
    @api_router.post("/api/v1/auth/unlock")
    def auth_unlock(
        payload: AuthUnlockRequest,
        response: Response,
        device_id: str = Depends(get_current_device_id),
    ):
        success, message = svc.authenticate(payload.password)
        if not success:
            lockout_info = svc.get_lockout_status()
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": message,
                    "unlocked": False,
                    "lockout": lockout_info,
                },
            )

        token = sess_mgr.create_session(device_id)
        response.set_cookie(
            key="scm_session",
            value=token,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return {"unlocked": True, "token": token, "session_token": token}

    @api_router.get("/api/v1/auth/status")
    def auth_status():
        unlocked = svc.is_unlocked()
        lockout_info = svc.get_lockout_status()
        return {"unlocked": unlocked, "lockout": lockout_info}

    @api_router.post("/api/v1/auth/lock")
    def auth_lock(
        request: Request,
        response: Response,
        x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    ):
        token = request.cookies.get("scm_session") or x_session_token
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()

        if token:
            sess_mgr.terminate_session(token)
        svc.lock_vault()

        response.delete_cookie(key="scm_session", path="/")
        return {"unlocked": False}

    # Secret CRUD Endpoints
    @api_router.get("/api/v1/secrets")
    def list_secrets(
        filter: Optional[str] = Query(None, alias="filter"),
        _session: str = Depends(require_session),
    ):
        records = svc.get_secret_records(filter or "")
        return [r.to_dict() for r in records]

    @api_router.get("/api/v1/secrets/{name}")
    def get_secret(
        name: str,
        _session: str = Depends(require_session),
    ):
        secret = svc.get_secret(name)
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Secret '{name}' not found",
            )
        return secret.to_dict()

    @api_router.post("/api/v1/secrets", status_code=status.HTTP_201_CREATED)
    def create_secret(
        payload: SecretCreateRequest,
        _session: str = Depends(require_session),
    ):
        try:
            svc.add_secret(
                name=payload.name,
                username=payload.username,
                password=payload.password,
                url=payload.url,
                comments=payload.comments,
                category=payload.category,
                is_favorite=payload.is_favorite,
                totp_secret=payload.totp_secret,
                tags=payload.tags,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        return {"status": "created", "name": payload.name}

    @api_router.put("/api/v1/secrets/{name}")
    def update_secret(
        name: str,
        payload: SecretUpdateRequest,
        _session: str = Depends(require_session),
    ):
        try:
            kwargs = {}
            if payload.name is not None:
                kwargs["new_name"] = payload.name
            if payload.username is not None:
                kwargs["username"] = payload.username
            if payload.password is not None:
                kwargs["password"] = payload.password
            if payload.url is not None:
                kwargs["url"] = payload.url
            if payload.comments is not None:
                kwargs["comments"] = payload.comments
            if payload.category is not None:
                kwargs["category"] = payload.category
            if payload.is_favorite is not None:
                kwargs["is_favorite"] = payload.is_favorite
            if payload.totp_secret is not None:
                kwargs["totp_secret"] = payload.totp_secret
            if payload.tags is not None:
                kwargs["tags"] = payload.tags

            svc.update_secret(original_name=name, **kwargs)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Secret '{name}' not found",
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        return {"status": "updated", "name": payload.name or name}

    @api_router.delete("/api/v1/secrets/{name}")
    def delete_secret(
        name: str,
        _session: str = Depends(require_session),
    ):
        try:
            svc.delete_secret(name)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Secret '{name}' not found",
            )
        return {"status": "deleted", "name": name}

    # TOTP Calculation Endpoint
    @api_router.get("/api/v1/totp/{name}")
    def get_totp(
        name: str,
        _session: str = Depends(require_session),
    ):
        secret = svc.get_secret(name)
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Secret '{name}' not found",
            )
        totp_secret = secret.get_totp_secret()
        if not totp_secret:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No TOTP secret configured for '{name}'",
            )
        try:
            totp_info = TotpService.generate_totp(totp_secret)
            return totp_info
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to generate TOTP: {exc}",
            )

    # Mount routes on root and on subpath prefix if provided
    # Static Files and HTML Dashboard routes
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @api_router.get("/")
    def serve_dashboard():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"status": "ok", "app": "Simple Credential Manager"}

    @api_router.get("/style.css")
    def serve_style():
        f = static_dir / "style.css"
        if f.exists():
            return FileResponse(f, media_type="text/css")
        raise HTTPException(status_code=404)

    @api_router.get("/app.js")
    def serve_js():
        f = static_dir / "app.js"
        if f.exists():
            return FileResponse(f, media_type="application/javascript")
        raise HTTPException(status_code=404)

    @api_router.get("/favicon.ico")
    def serve_favicon():
        return Response(status_code=204)

    @api_router.get("/enroll")
    def serve_enrollment():
        if not svc.is_initialized():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vault is not initialized. Please set up the master password on the server first.",
            )
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"status": "enrollment_page_placeholder"}

    @api_router.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(api_router)
    if normalized_prefix:
        app.include_router(api_router, prefix=normalized_prefix)

    # Device Gatekeeper Middleware
    @app.middleware("http")
    async def device_gatekeeper(request: Request, call_next):
        path = request.url.path

        # If mounted behind root_path, subpath prefix, or reverse-proxy X-Forwarded-Prefix
        subpath = path
        effective_prefix = normalized_prefix
        forwarded_prefix = request.headers.get("X-Forwarded-Prefix", "").rstrip("/")
        if forwarded_prefix and subpath.startswith(forwarded_prefix):
            effective_prefix = forwarded_prefix

        if effective_prefix and subpath.startswith(effective_prefix):
            subpath = subpath[len(effective_prefix):] or "/"

        # If request has X-Forwarded-Prefix, rewrite scope['path'] to stripped subpath so router matches
        if forwarded_prefix and path.startswith(forwarded_prefix):
            request.scope["path"] = subpath

        exempt_prefixes = (
            "/healthz",
            "/style.css",
            "/app.js",
            "/favicon.ico",
            "/enroll",
            "/api/v1/devices/enroll",
            "/docs",
            "/openapi.json",
            "/static/",
        )
        exempt_exact = (
            "/",
            "/healthz",
            "/style.css",
            "/app.js",
            "/favicon.ico",
            "/enroll",
            "/api/v1/devices/enroll",
            "/docs",
            "/openapi.json",
        )

        is_exempt = subpath in exempt_exact or any(subpath.startswith(p) for p in exempt_prefixes)

        if not is_exempt:
            device_token = request.headers.get("X-Device-Token")
            if not device_token or not reg.is_device_approved(device_token):
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Service unavailable"},
                )

        # Transport Payload Decryption for POST/PUT requests
        if request.method in ("POST", "PUT", "PATCH"):
            body_bytes = await request.body()
            if body_bytes:
                try:
                    payload = json.loads(body_bytes.decode("utf-8"))
                    if isinstance(payload, dict) and "iv" in payload and "ciphertext" in payload:
                        device_token = request.headers.get("X-Device-Token")
                        if not device_token:
                            return JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content={"detail": "Device token required for encrypted payload"},
                            )
                        try:
                            decrypted_data = decrypt_payload(payload, device_token)
                        except Exception as exc:
                            return JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content={"detail": f"Failed to decrypt transport payload: {exc}"},
                            )
                        if isinstance(decrypted_data, (dict, list)):
                            new_body = json.dumps(decrypted_data).encode("utf-8")
                        elif isinstance(decrypted_data, str):
                            new_body = decrypted_data.encode("utf-8")
                        else:
                            new_body = json.dumps(decrypted_data).encode("utf-8")

                        # Clear cached body and json on request so downstream parses the new body
                        request._body = new_body
                        if hasattr(request, "_json"):
                            delattr(request, "_json")

                        async def receive():
                            return {"type": "http.request", "body": new_body, "more_body": False}

                        request._receive = receive
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Standard non-JSON body, proceed normally
                    pass

        response = await call_next(request)
        return response

    return app
