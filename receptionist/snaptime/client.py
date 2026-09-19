"""HTTP client for the Snaptime `/api/ai/*` service API."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("receptionist.snaptime")


class SnaptimeClient:
    def __init__(self, base_url: str, token: str, *, timeout: float = 8.0) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout

    @classmethod
    def from_env(cls) -> "SnaptimeClient | None":
        base = (os.environ.get("SNAPTIME_API_BASE") or "").strip().strip("'\"")
        token = (os.environ.get("AI_SERVICE_TOKEN") or "").strip().strip("'\"")
        if not base or not token:
            return None
        return cls(base, token)

    async def _request(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                res = await http.request(method, f"{self._base}{path}", json=body, headers=self._headers)
            if res.status_code >= 400:
                logger.error("snaptime %s %s -> %s", method, path, res.status_code)
                return None
            return res.json()
        except Exception:
            logger.exception("snaptime %s %s failed", method, path)
            return None

    async def get_config(self) -> dict[str, Any] | None:
        return await self._request("GET", "/api/ai/config", None)

    async def start_call(self, *, call_id: str, phone_number: str | None, caller_number: str | None, engine: str) -> dict[str, Any] | None:
        return await self._request("POST", "/api/ai/calls", {
            "externalCallId": call_id, "phoneNumber": phone_number, "callerNumber": caller_number, "engine": engine,
        })

    async def end_call(self, call_id: str, **fields: Any) -> None:
        await self._request("PATCH", f"/api/ai/calls/{call_id}", fields)

    async def lookup_session_by_code(self, *, call_id: str, code: str) -> dict[str, Any] | None:
        return await self._request("POST", "/api/ai/tools/lookup-session-by-code", {"callId": call_id, "code": code})

    async def identify_photographer(self, *, call_id: str, caller_number: str | None) -> dict[str, Any] | None:
        return await self._request("POST", "/api/ai/tools/identify-photographer", {"callId": call_id, "callerNumber": caller_number})

    async def create_callback_request(self, *, call_id: str, caller_name: str | None, callback_number: str, message: str) -> dict[str, Any] | None:
        return await self._request("POST", "/api/ai/tools/create-callback-request", {
            "callId": call_id, "callerName": caller_name, "callerNumber": callback_number, "message": message,
        })
