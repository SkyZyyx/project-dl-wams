from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings


class OrderServiceError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 502, payload: dict | list | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.payload = payload


def proxy_order_request(
    *,
    method: str,
    path: str,
    body: bytes = b"",
    content_type: str = "application/json",
    authorization: str | None = None,
) -> tuple[int, dict | list]:
    url = f"{settings.ORDER_SERVICE_URL.rstrip('/')}{path}"
    headers = {"Accept": "application/json", "Content-Type": content_type}
    if authorization:
        headers["Authorization"] = authorization

    upper_method = method.upper()
    request = urllib_request.Request(
        url,
        data=(None if upper_method == "GET" else body),
        headers=headers,
        method=upper_method,
    )
    try:
        with urllib_request.urlopen(request, timeout=settings.UPSTREAM_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return response.getcode(), payload
    except urllib_error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw or f"order service returned {exc.code}"}
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise OrderServiceError(
            detail or "order service request failed",
            status_code=exc.code,
            payload=payload,
        ) from exc
    except (urllib_error.URLError, json.JSONDecodeError) as exc:
        raise OrderServiceError("order service request failed", status_code=502) from exc
