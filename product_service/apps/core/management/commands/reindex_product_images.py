from __future__ import annotations

from django.core.management import BaseCommand

from apps.products.models import ProductImage
from apps.products.services.search_proxy import SearchServiceError, index_product_image


class Command(BaseCommand):
    help = "Index existing product images in the search service."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Re-index every image, including images already marked indexed.",
        )

    def handle(self, *args, **options):
        queryset = ProductImage.objects.select_related("product").exclude(image="")
        if not options["all"]:
            queryset = queryset.filter(indexed=False)

        total = queryset.count()
        indexed = 0
        skipped = 0

        for image in queryset.iterator():
            try:
                with image.image.open("rb") as image_file:
                    response = index_product_image(
                        product_id=image.product_id,
                        product_image_id=image.id,
                        image_name=image.image.name.rsplit("/", 1)[-1],
                        image_bytes=image_file.read(),
                        content_type=getattr(image.image.file, "content_type", "application/octet-stream"),
                    )
            except (SearchServiceError, FileNotFoundError, OSError) as exc:
                skipped += 1
                self.stderr.write(
                    self.style.WARNING(f"Skipped product image {image.pk}: {exc}")
                )
                continue

            ProductImage.objects.filter(pk=image.pk).update(indexed=True, qdrant_id=response.get("qdrant_id"))
            indexed += 1
            self.stdout.write(f"Indexed {indexed}/{total}: product image {image.pk}")

        self.stdout.write(self.style.SUCCESS(f"Indexed {indexed} product image(s); skipped {skipped}."))
