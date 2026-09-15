from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_TIMEOUT_S = 180


class ApiError(Exception):
    def __init__(self, status: int, message: str, service: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.service = service

    def __str__(self) -> str:
        return f"{self.service}: {self.message}" if self.service else self.message


def request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method=method, headers={**headers, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, _error_message(e)) from None
    except urllib.error.URLError as e:
        raise ApiError(0, f"network error: {e.reason}") from None
    except (socket.timeout, TimeoutError):
        raise ApiError(0, f"no response after {timeout:g}s") from None
    except ValueError:
        raise ApiError(0, "response wasn't valid JSON") from None


def _error_message(error: urllib.error.HTTPError) -> str:
    try:
        payload = json.load(error)
    except (ValueError, OSError):
        return str(error.reason)
    if isinstance(payload, dict):
        inner = payload.get("error")
        if isinstance(inner, dict) and inner.get("message"):
            return str(inner["message"])
        if payload.get("message"):
            return str(payload["message"])
    return str(error.reason)
