from __future__ import annotations

from django.core.management import BaseCommand

from apps.products.models import ProductImage
from apps.products.lifecycle import index_product_image_record
from apps.products.services.search_proxy import SearchServiceError


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
                index_product_image_record(image)
            except (SearchServiceError, FileNotFoundError, OSError) as exc:
                skipped += 1
                self.stderr.write(
                    self.style.WARNING(f"Skipped product image {image.pk}: {exc}")
                )
                continue

            indexed += 1
            self.stdout.write(f"Indexed {indexed}/{total}: product image {image.pk}")

        self.stdout.write(self.style.SUCCESS(f"Indexed {indexed} product image(s); skipped {skipped}."))
