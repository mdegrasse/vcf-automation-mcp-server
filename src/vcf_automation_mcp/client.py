from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any

import httpx

from .config import Settings

# Access tokens are documented as expiring after one hour; refresh this many
# seconds early to avoid racing a request against expiry.
TOKEN_REFRESH_SKEW_SECONDS = 60
# Fallback lifetime when the token response doesn't include expires_in.
DEFAULT_TOKEN_LIFETIME_SECONDS = 3300


class VCFAAuthError(RuntimeError):
    pass


class VCFAAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str, body: Any = None):
        super().__init__(f"VCF Automation API error {status_code}: {message}")
        self.status_code = status_code
        self.body = body


class Service(str, Enum):
    """The VCF Automation services this client talks to, each with its own API path
    prefix and independently versioned ?apiVersion= query parameter."""

    IAAS = "iaas"
    CATALOG = "catalog"
    DEPLOYMENT = "deployment"


_SERVICE_PREFIX = {
    Service.IAAS: "/iaas/api",
    Service.CATALOG: "/catalog/api",
    Service.DEPLOYMENT: "/deployment/api",
}


class VCFAClient:
    """Async client for the VCF Automation (Aria Automation) REST API.

    Authenticates with a long-lived API refresh token (generated once in the VCF
    Automation UI under My Account > API Tokens) which is exchanged here for
    short-lived bearer access tokens, cached and transparently renewed.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            verify=settings.verify_ssl,
            timeout=settings.timeout,
            headers={"Accept": "application/json"},
        )
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._auth_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "VCFAClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # -- authentication -----------------------------------------------

    def _token_url(self) -> str:
        if self._settings.token_url:
            return self._settings.token_url
        if self._settings.org:
            return f"/tm/oauth/tenant/{self._settings.org}/token"
        return "/oauth/provider/token"

    async def _acquire_token(self) -> None:
        response = await self._http.post(
            self._token_url(),
            data={"grant_type": "refresh_token", "refresh_token": self._settings.refresh_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code != 200:
            raise VCFAAuthError(
                f"Failed to exchange VCF Automation refresh token for an access token "
                f"(HTTP {response.status_code}): {response.text}"
            )
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise VCFAAuthError("Token response did not include an access_token")
        self._access_token = token
        expires_in = data.get("expires_in")
        if isinstance(expires_in, (int, float)):
            self._token_expires_at = time.time() + expires_in
        else:
            self._token_expires_at = time.time() + DEFAULT_TOKEN_LIFETIME_SECONDS

    async def _ensure_token(self) -> str:
        async with self._auth_lock:
            if not self._access_token or time.time() >= self._token_expires_at - TOKEN_REFRESH_SKEW_SECONDS:
                await self._acquire_token()
        assert self._access_token is not None
        return self._access_token

    # -- request plumbing -----------------------------------------------

    async def request(
        self,
        method: str,
        service: Service,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        token = await self._ensure_token()
        url = f"{_SERVICE_PREFIX[service]}{path}"
        request_params = _with_api_version(self._settings, service, params)
        response = await self._http.request(
            method,
            url,
            params=request_params,
            json=json,
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code == 401:
            # Access token may have been invalidated server-side; force one refresh and retry.
            async with self._auth_lock:
                self._access_token = None
            token = await self._ensure_token()
            response = await self._http.request(
                method,
                url,
                params=request_params,
                json=json,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 204:
            return None
        if not response.is_success:
            try:
                body = response.json()
                message = body.get("message") or body.get("errorMessage", response.text)
            except ValueError:
                body = response.text
                message = response.text
            raise VCFAAPIError(response.status_code, message, body)

        if not response.content:
            return None
        return response.json()

    async def get(self, service: Service, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", service, path, params=params)

    async def post(
        self, service: Service, path: str, *, params: dict[str, Any] | None = None, json: Any = None
    ) -> Any:
        return await self.request("POST", service, path, params=params, json=json)

    async def delete(self, service: Service, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self.request("DELETE", service, path, params=params)


def _with_api_version(settings: Settings, service: Service, params: dict[str, Any] | None) -> dict[str, Any]:
    api_version = {
        Service.IAAS: settings.api_version_iaas,
        Service.CATALOG: settings.api_version_catalog,
        Service.DEPLOYMENT: settings.api_version_deployment,
    }[service]
    cleaned = _clean_params(params) or {}
    cleaned.setdefault("apiVersion", api_version)
    return cleaned


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop None values and normalize bools so httpx encodes them the way the API expects."""
    if not params:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = str(value).lower()
        else:
            cleaned[key] = value
    return cleaned or None
