from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.conf import settings


class AuthServiceError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _auth_url(path: str) -> str:
    return f"{settings.USER_SERVICE_URL.rstrip('/')}/api/auth/{path.lstrip('/')}"


def proxy_auth_post(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(
        _auth_url(path),
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(request, timeout=settings.UPSTREAM_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="ignore")
        detail = response_body or f"auth service returned {exc.code}"
        raise AuthServiceError(detail=detail, status_code=exc.code) from exc
    except (urllib_error.URLError, json.JSONDecodeError) as exc:
        raise AuthServiceError("auth service request failed", status_code=502) from exc


def proxy_auth_profile(bearer_token: str) -> dict:
    request = urllib_request.Request(
        _auth_url("profile/"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {bearer_token}",
        },
        method="GET",
    )
    try:
        with urllib_request.urlopen(request, timeout=settings.UPSTREAM_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="ignore")
        detail = response_body or f"auth service returned {exc.code}"
        raise AuthServiceError(detail=detail, status_code=exc.code) from exc
    except (urllib_error.URLError, json.JSONDecodeError) as exc:
        raise AuthServiceError("auth service request failed", status_code=502) from exc
