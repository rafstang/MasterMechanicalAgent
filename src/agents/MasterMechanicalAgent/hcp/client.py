"""Async HTTP client for the HouseCall Pro Public API."""

from __future__ import annotations

import os
from typing import Any

import httpx

HCP_API_BASE = "https://api.housecallpro.com"
DEFAULT_TIMEOUT_SECONDS = 30.0


class HcpApiError(Exception):
    """Raised when the HouseCall Pro API returns an error response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class HcpClient:
    """Thin async wrapper around HouseCall Pro REST endpoints used by the agent."""

    def __init__(self, api_key: str | None = None) -> None:
        key = (api_key if api_key is not None else os.getenv("HOUSECALL_PRO_API_KEY") or "").strip()
        if not key:
            raise HcpApiError(
                "HOUSECALL_PRO_API_KEY is not configured on the server."
            )
        self._api_key = key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _unwrap_resource(payload: dict[str, Any], resource_key: str) -> dict[str, Any]:
        nested = payload.get(resource_key)
        if isinstance(nested, dict):
            return nested
        if isinstance(payload, dict) and "id" in payload:
            return payload
        return payload

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{HCP_API_BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                )
        except httpx.HTTPError as exc:
            raise HcpApiError(
                "Could not reach HouseCall Pro. Check network connectivity and try again."
            ) from exc

        if response.status_code >= 400:
            detail = _sanitize_api_error_body(response.text)
            raise HcpApiError(
                f"HouseCall Pro API error ({response.status_code}): {detail}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        data = response.json()
        if not isinstance(data, dict):
            raise HcpApiError("Unexpected response format from HouseCall Pro.")
        return data

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/customers/{customer_id}")
        return self._unwrap_resource(data, "customer")

    async def get_job(self, job_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/jobs/{job_id}")
        return self._unwrap_resource(data, "job")

    async def patch_customer(self, customer_id: str, body: dict[str, Any]) -> dict[str, Any]:
        data = await self._request(
            "PATCH",
            f"/customers/{customer_id}",
            json_body=body,
        )
        return self._unwrap_resource(data, "customer")

    async def patch_job(self, job_id: str, body: dict[str, Any]) -> dict[str, Any]:
        data = await self._request(
            "PATCH",
            f"/jobs/{job_id}",
            json_body=body,
        )
        return self._unwrap_resource(data, "job")


def _sanitize_api_error_body(text: str, *, max_len: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned or "request failed"
