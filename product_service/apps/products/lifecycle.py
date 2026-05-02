from __future__ import annotations

import logging
from time import sleep

from .models import ProductImage
from .services.search_proxy import SearchServiceError, delete_product_index, index_product_image


logger = logging.getLogger(__name__)
_logged_search_unavailable: set[str] = set()


def log_search_unavailable_once(key: str, message: str, *args):
    if key in _logged_search_unavailable:
        logger.debug(message, *args)
        return
    _logged_search_unavailable.add(key)
    logger.warning(message, *args)


def _index_image(image: ProductImage):
    with image.image.open("rb") as image_file:
        response = index_product_image(
            product_id=image.product_id,
            product_image_id=image.id,
            image_name=image.image.name.rsplit("/", 1)[-1],
            image_bytes=image_file.read(),
            content_type=getattr(image.image.file, "content_type", "application/octet-stream"),
        )

    ProductImage.objects.filter(pk=image.pk).update(indexed=True, qdrant_id=response.get("qdrant_id"))


def index_product_image_record(image: ProductImage, *, retries: int = 3, retry_delay_seconds: float = 1.5):
    last_error: SearchServiceError | None = None
    for attempt in range(1, retries + 1):
        try:
            _index_image(image)
            return
        except SearchServiceError as exc:
            last_error = exc
            should_retry = exc.status_code is None or exc.status_code >= 500
            if not should_retry or attempt >= retries:
                raise
            logger.warning(
                "Search service not ready for product image %s (attempt %s/%s): %s",
                image.pk,
                attempt,
                retries,
                exc,
            )
            sleep(retry_delay_seconds * attempt)

    if last_error is not None:
        raise last_error


def refresh_product_image_vectors(product_id: int):
    try:
        delete_product_index(product_id)
        for image in ProductImage.objects.filter(product_id=product_id).select_related("product"):
            if not image.image:
                continue
            index_product_image_record(image)
    except SearchServiceError:
        log_search_unavailable_once("refresh", "Search service unavailable; skipped vector refresh after image delete")


def delete_product_vectors(product_id: int):
    try:
        delete_product_index(product_id)
    except SearchServiceError:
        log_search_unavailable_once("delete", "Search service unavailable; skipped vector deletes")
