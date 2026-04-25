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


def fetch_products_by_ids(product_ids: list[int]) -> list[dict]:
    if not product_ids:
        return []

    query = urllib_parse.urlencode({"ids": ",".join(str(product_id) for product_id in product_ids)})
    url = f"{settings.PRODUCT_SERVICE_URL.rstrip('/')}/api/products/?{query}"
    try:
        payload = _json_request(url)
    except (urllib_error.HTTPError, urllib_error.URLError, json.JSONDecodeError) as exc:
        raise CatalogServiceError("product service request failed") from exc

    if isinstance(payload, list):
        return payload
    raise CatalogServiceError("unexpected product service payload")
