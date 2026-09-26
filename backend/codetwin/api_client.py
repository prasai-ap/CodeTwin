"""Small HTTP client used by IBM Bob's separate stdio MCP process."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_api(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    """Call CodeTwin's configured FastAPI origin without a built-in host fallback."""
    base_url = os.getenv("CODETWIN_API_BASE_URL", "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("Set CODETWIN_API_BASE_URL to the reachable CodeTwin API origin before starting IBM Bob")

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url}{path}",
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    try:
        with urlopen(request, timeout=180) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("detail", error.reason)
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            detail = error.reason
        raise ValueError(f"CodeTwin API returned HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        raise ValueError(f"Could not reach the CodeTwin API at CODETWIN_API_BASE_URL: {error}") from error

    if not isinstance(decoded, dict):
        raise ValueError("CodeTwin API returned an unexpected response")
    return decoded
