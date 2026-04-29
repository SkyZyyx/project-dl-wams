from __future__ import annotations

from collections.abc import Iterable

from ..models import OrderItem
from .catalog_client import CatalogServiceError, fetch_products_by_ids


def build_product_map(orders: Iterable) -> dict[int, dict]:
    product_ids: list[int] = []
    for order in orders:
        for item in order.items.all():
            if item.product_id not in product_ids:
                product_ids.append(item.product_id)

    if not product_ids:
        return {}

    try:
        products = fetch_products_by_ids(product_ids)
    except CatalogServiceError:
        return {}

    return {int(product["id"]): product for product in products if product.get("id") is not None}


def product_payload(item: OrderItem, product_map: dict[int, dict] | None = None) -> dict:
    live_map = product_map or {}
    payload = live_map.get(item.product_id)
    if payload is not None:
        return payload

    category = None
    if item.product_category_id is not None:
        category = {
            "id": item.product_category_id,
            "name": item.product_category_name,
            "slug": item.product_category_slug,
        }

    return {
        "id": item.product_id,
        "name": item.product_name,
        "description": item.product_description,
        "price": str(item.unit_price),
        "category": category,
    }
