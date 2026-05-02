from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.conf import settings


class CatalogServiceError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 502, payload: dict | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.payload = payload


def _json_request(url: str) -> list[dict] | dict:
    request = urllib_request.Request(url, headers={"Accept": "application/json"})
    with urllib_request.urlopen(request, timeout=settings.UPSTREAM_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _gateway_media_url(url: str | None) -> str | None:
    if not url:
        return url

    parsed = urllib_parse.urlparse(url)
    if parsed.path.startswith(settings.MEDIA_URL):
        return parsed.path
    return url


def _normalize_products(payload: list[dict] | dict) -> list[dict]:
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        products = payload["results"]
    elif isinstance(payload, list):
        products = payload
    else:
        raise CatalogServiceError("unexpected product service payload")

    for product in products:
        for image in product.get("images", []):
            image["image_url"] = _gateway_media_url(image.get("image_url"))
    return products


def fetch_products(product_ids: list[int] | None = None) -> list[dict]:
    query = ""
    if product_ids:
        query = "?" + urllib_parse.urlencode({"ids": ",".join(str(product_id) for product_id in product_ids)})

    url = f"{settings.PRODUCT_SERVICE_URL.rstrip('/')}/api/products/{query}"
    try:
        payload = _json_request(url)
    except (urllib_error.HTTPError, urllib_error.URLError, json.JSONDecodeError) as exc:
        raise CatalogServiceError("product service request failed") from exc

    return _normalize_products(payload)


def fetch_products_by_ids(product_ids: list[int]) -> list[dict]:
    if not product_ids:
        return []
    return fetch_products(product_ids)


def proxy_catalog_write(
    *,
    method: str,
    path: str,
    body: bytes,
    content_type: str,
    authorization: str | None = None,
) -> tuple[int, dict]:
    url = f"{settings.PRODUCT_SERVICE_URL.rstrip('/')}{path}"
    headers = {"Accept": "application/json", "Content-Type": content_type}
    if authorization:
        headers["Authorization"] = authorization
    upper_method = method.upper()
    request = urllib_request.Request(url, data=(None if upper_method == "GET" else body), headers=headers, method=upper_method)
    try:
        with urllib_request.urlopen(request, timeout=settings.UPSTREAM_TIMEOUT_SECONDS) as response:
            status_code = response.getcode()
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return status_code, payload
    except urllib_error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"detail": raw or f"product service returned {exc.code}"}
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if detail is None and isinstance(payload, dict) and payload:
            detail = "; ".join(
                f"{key}: {', '.join(str(item) for item in value) if isinstance(value, list) else value}"
                for key, value in payload.items()
            )
        raise CatalogServiceError(
            detail or "product service request failed",
            status_code=exc.code,
            payload=payload if isinstance(payload, dict) else None,
        ) from exc
    except (urllib_error.URLError, json.JSONDecodeError) as exc:
        raise CatalogServiceError("product service request failed", status_code=502) from exc
