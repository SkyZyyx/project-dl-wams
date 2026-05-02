from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request
from uuid import uuid4

from django.conf import settings


class SearchServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _error_detail(exc: Exception, fallback: str) -> str:
    if isinstance(exc, urllib_error.HTTPError):
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        if body:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return f"{fallback}: HTTP {exc.code}: {body[:500]}"
            detail = payload.get("detail") if isinstance(payload, dict) else None
            if detail:
                return f"{fallback}: {detail}"
        return f"{fallback}: HTTP {exc.code}"
    if isinstance(exc, urllib_error.URLError):
        return f"{fallback}: {exc.reason}"
    return fallback


def _multipart_body(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]):
    boundary = f"----wams-{uuid4().hex}"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        parts.append(str(value).encode("utf-8"))
        parts.append(b"\r\n")

    for name, (filename, content, content_type) in files.items():
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        parts.append(content)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def _json_request(method: str, url: str, *, body: bytes | None = None, headers: dict[str, str] | None = None):
    request_headers = {"Host": settings.SEARCH_SERVICE_HOST_HEADER}
    request_headers.update(headers or {})
    request = urllib_request.Request(url, data=body, headers=request_headers, method=method)
    with urllib_request.urlopen(request, timeout=settings.SEARCH_SERVICE_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def index_product_image(*, product_id: int, product_image_id: int, image_name: str, image_bytes: bytes, content_type: str) -> dict:
    body, boundary = _multipart_body(
        fields={"product_id": str(product_id), "product_image_id": str(product_image_id)},
        files={"image": (image_name, image_bytes, content_type or "application/octet-stream")},
    )
    url = f"{settings.SEARCH_SERVICE_URL.rstrip('/')}/api/index/"
    try:
        return _json_request(
            "POST",
            url,
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
        )
    except (urllib_error.HTTPError, urllib_error.URLError, json.JSONDecodeError) as exc:
        status_code = exc.code if isinstance(exc, urllib_error.HTTPError) else None
        raise SearchServiceError(_error_detail(exc, "index request failed"), status_code=status_code) from exc


def delete_product_index(product_id: int) -> dict:
    url = f"{settings.SEARCH_SERVICE_URL.rstrip('/')}/api/index/{product_id}/"
    try:
        return _json_request("DELETE", url, headers={"Accept": "application/json"})
    except (urllib_error.HTTPError, urllib_error.URLError, json.JSONDecodeError) as exc:
        status_code = exc.code if isinstance(exc, urllib_error.HTTPError) else None
        raise SearchServiceError(_error_detail(exc, "delete request failed"), status_code=status_code) from exc
