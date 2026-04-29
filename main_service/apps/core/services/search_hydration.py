from __future__ import annotations

from collections.abc import Callable


def hydrate_search_matches(
    search_payload: dict,
    *,
    fetch_products_by_ids: Callable[[list[int]], list[dict]],
    max_results: int = 10,
    on_missing_products: Callable[[list[int]], None] | None = None,
) -> tuple[list[dict], str | None]:
    matches = search_payload.get("matches", [])
    detail = search_payload.get("detail")

    if not matches:
        return [], detail

    product_ids: list[int] = []
    best_matches: dict[int, dict] = {}

    for match in matches:
        product_id = match.get("product_id")
        if product_id is None:
            continue

        score = float(match.get("score") or 0)
        current = best_matches.get(product_id)
        if current is None or score > current["score"]:
            best_matches[product_id] = {
                "product_id": product_id,
                "product_image_id": match.get("product_image_id"),
                "qdrant_id": match.get("qdrant_id"),
                "score": score,
            }
        if product_id not in product_ids:
            product_ids.append(product_id)

    products_payload = fetch_products_by_ids(product_ids)
    products_by_id = {int(product["id"]): product for product in products_payload if product.get("id") is not None}

    missing_product_ids = [product_id for product_id in product_ids if product_id not in products_by_id]
    if missing_product_ids and on_missing_products is not None:
        on_missing_products(missing_product_ids)

    hydrated_matches = []
    for product_id in product_ids:
        product = products_by_id.get(product_id)
        match = best_matches.get(product_id)
        if product is None or match is None:
            continue

        product_data = dict(product)
        product_data.update(
            {
                "score": match["score"],
                "product_image_id": match["product_image_id"],
                "qdrant_id": match["qdrant_id"],
            }
        )
        hydrated_matches.append(product_data)

    hydrated_matches.sort(key=lambda item: item.get("score", 0), reverse=True)
    return hydrated_matches[:max_results], None
