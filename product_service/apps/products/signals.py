from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .lifecycle import (
    delete_product_vectors,
    index_product_image_record,
    log_search_unavailable_once,
    refresh_product_image_vectors,
)
from .models import Product, ProductImage
from .services.search_proxy import SearchServiceError


@receiver(post_save, sender=ProductImage)
def auto_index_product_image(sender, instance: ProductImage, created: bool, **kwargs):
    if not created or not instance.image:
        return

    try:
        index_product_image_record(instance)
    except SearchServiceError:
        log_search_unavailable_once("index", "Search service unavailable; skipped indexing product images")


@receiver(post_delete, sender=ProductImage)
def remove_vectors_on_image_delete(sender, instance: ProductImage, **kwargs):
    refresh_product_image_vectors(instance.product_id)


@receiver(post_delete, sender=Product)
def remove_vectors_on_product_delete(sender, instance: Product, **kwargs):
    delete_product_vectors(instance.pk)
