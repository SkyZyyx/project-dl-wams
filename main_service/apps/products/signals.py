from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Product, ProductImage
from .services.search_proxy import SearchServiceError, delete_product_index, index_product_image


logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProductImage)
def auto_index_product_image(sender, instance: ProductImage, created: bool, **kwargs):
    if not created or not instance.image:
        return

    def _index():
        try:
            with instance.image.open("rb") as image_file:
                response = index_product_image(
                    product_id=instance.product_id,
                    product_image_id=instance.id,
                    image_name=instance.image.name.rsplit("/", 1)[-1],
                    image_bytes=image_file.read(),
                    content_type=getattr(instance.image.file, "content_type", "application/octet-stream"),
                )
            ProductImage.objects.filter(pk=instance.pk).update(indexed=True, qdrant_id=response.get("qdrant_id"))
        except SearchServiceError:
            logger.exception("Failed to auto-index product image %s", instance.pk)

    _index()


@receiver(post_delete, sender=ProductImage)
def remove_vectors_on_image_delete(sender, instance: ProductImage, **kwargs):
    try:
        delete_product_index(instance.product_id)
    except SearchServiceError:
        logger.exception("Failed to delete vectors for product %s after image delete", instance.product_id)


@receiver(post_delete, sender=Product)
def remove_vectors_on_product_delete(sender, instance: Product, **kwargs):
    try:
        delete_product_index(instance.pk)
    except SearchServiceError:
        logger.exception("Failed to delete vectors for product %s", instance.pk)
