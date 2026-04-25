from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.conf import settings


class CatalogServiceError(RuntimeError):
    pass


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
