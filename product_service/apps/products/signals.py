from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Product, ProductImage
from .services.search_proxy import SearchServiceError, delete_product_index, index_product_image


logger = logging.getLogger(__name__)
_logged_search_unavailable: set[str] = set()


def _log_search_unavailable_once(key: str, message: str, *args):
    if key in _logged_search_unavailable:
        logger.debug(message, *args)
        return
    _logged_search_unavailable.add(key)
    logger.warning(message, *args)


def _index_image_by_pk(image_pk: int):
    image = ProductImage.objects.select_related("product").get(pk=image_pk)
    with image.image.open("rb") as image_file:
        response = index_product_image(
            product_id=image.product_id,
            product_image_id=image.id,
            image_name=image.image.name.rsplit("/", 1)[-1],
            image_bytes=image_file.read(),
            content_type=getattr(image.image.file, "content_type", "application/octet-stream"),
        )
    ProductImage.objects.filter(pk=image.pk).update(indexed=True, qdrant_id=response.get("qdrant_id"))


@receiver(post_save, sender=ProductImage)
def auto_index_product_image(sender, instance: ProductImage, created: bool, **kwargs):
    if not created or not instance.image:
        return

    try:
        _index_image_by_pk(instance.pk)
    except SearchServiceError:
        _log_search_unavailable_once("index", "Search service unavailable; skipped indexing product images")


@receiver(post_delete, sender=ProductImage)
def remove_vectors_on_image_delete(sender, instance: ProductImage, **kwargs):
    try:
        delete_product_index(instance.product_id)
        for image_pk in ProductImage.objects.filter(product_id=instance.product_id).values_list("pk", flat=True):
            _index_image_by_pk(image_pk)
    except SearchServiceError:
        _log_search_unavailable_once("refresh", "Search service unavailable; skipped vector refresh after image delete")


@receiver(post_delete, sender=Product)
def remove_vectors_on_product_delete(sender, instance: Product, **kwargs):
    try:
        delete_product_index(instance.pk)
    except SearchServiceError:
        _log_search_unavailable_once("delete", "Search service unavailable; skipped vector deletes")
