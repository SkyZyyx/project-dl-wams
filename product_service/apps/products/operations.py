from __future__ import annotations

from dataclasses import dataclass

from .lifecycle import index_product_image_record
from .models import Category, Product, ProductImage
from .services.search_proxy import SearchServiceError


@dataclass(frozen=True)
class ProductCatalogStats:
    categories: int
    products: int
    images: int
    indexed_images: int


def get_catalog_stats() -> ProductCatalogStats:
    return ProductCatalogStats(
        categories=Category.objects.count(),
        products=Product.objects.count(),
        images=ProductImage.objects.count(),
        indexed_images=ProductImage.objects.filter(indexed=True).count(),
    )


def delete_product(product_id: int) -> bool:
    deleted_count, _ = Product.objects.filter(pk=product_id).delete()
    return deleted_count > 0


def delete_all_products() -> int:
    deleted_count, _ = Product.objects.all().delete()
    return deleted_count


def reindex_all_product_images() -> tuple[int, int]:
    indexed = 0
    skipped = 0

    for image in ProductImage.objects.select_related("product").exclude(image="").iterator():
        try:
            index_product_image_record(image)
        except (SearchServiceError, FileNotFoundError, OSError):
            skipped += 1
            continue

        indexed += 1

    return indexed, skipped
