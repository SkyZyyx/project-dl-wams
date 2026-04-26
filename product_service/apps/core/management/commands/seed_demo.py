from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
import random
import re
from itertools import islice

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand, CommandError, call_command

from apps.products.models import Category, Product, ProductImage


DEMO_PREFIX = "Kaggle Cars"
DEFAULT_DATASET_ID = "jutrera/stanford-car-dataset-by-classes-folder"
DEFAULT_IMAGES_PER_PRODUCT = 5
MIN_IMAGES_PER_PRODUCT = 5
MAX_IMAGES_PER_PRODUCT = 10


@dataclass(frozen=True)
class DatasetItem:
    category: str
    image_path: Path


def _slugish_name(value: str) -> str:
    value = re.sub(r"[_-]+", " ", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value.title()


def _import_kagglehub():
    api_token = os.getenv("KAGGLE_API_TOKEN")
    if api_token and not os.getenv("KAGGLE_KEY"):
        os.environ["KAGGLE_KEY"] = api_token

    try:
        import kagglehub  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency issue
        raise CommandError(
            "kagglehub is not installed. Add it to the product_service requirements first."
        ) from exc
    return kagglehub


def _download_dataset(dataset_id: str) -> Path:
    kagglehub = _import_kagglehub()
    dataset_path = Path(kagglehub.dataset_download(dataset_id)).resolve()
    if not dataset_path.exists():
        raise CommandError(f"kagglehub returned a missing dataset path: {dataset_path}")
    return dataset_path


def _iter_dataset_items(dataset_root: Path) -> list[DatasetItem]:
    items: list[DatasetItem] = []
    for image_path in sorted(dataset_root.rglob("*")):
        if image_path.is_file() and image_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            category = _slugish_name(image_path.parent.name)
            items.append(DatasetItem(category=category, image_path=image_path))
    return items


def _chunked(items: list[DatasetItem], size: int) -> list[list[DatasetItem]]:
    chunks: list[list[DatasetItem]] = []
    iterator = iter(items)
    while chunk := list(islice(iterator, size)):
        chunks.append(chunk)
    return chunks


def _clear_demo_data() -> None:
    ProductImage.objects.filter(product__category__name__startswith=f"{DEMO_PREFIX} ").delete()
    Product.objects.filter(category__name__startswith=f"{DEMO_PREFIX} ").delete()
    Category.objects.filter(name__startswith=f"{DEMO_PREFIX} ").delete()


def _to_uploaded_file(image_path: Path, *, name: str) -> SimpleUploadedFile:
    content = image_path.read_bytes()
    suffix = image_path.suffix.lower() or ".jpg"
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return SimpleUploadedFile(f"{name}{suffix}", content, content_type=content_type)


class Command(BaseCommand):
    help = "Seed demo car products from the Kaggle Stanford car dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset-id",
            default=DEFAULT_DATASET_ID,
            help="KaggleHub dataset id to download.",
        )
        parser.add_argument(
            "--images-per-product",
            type=int,
            default=DEFAULT_IMAGES_PER_PRODUCT,
            help="Target number of images per seeded product.",
        )
        parser.add_argument(
            "--shuffle",
            action="store_true",
            help="Shuffle dataset items before seeding.",
        )

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        dataset_id = options["dataset_id"]
        images_per_product = options["images_per_product"]
        should_shuffle = options["shuffle"]

        if not MIN_IMAGES_PER_PRODUCT <= images_per_product <= MAX_IMAGES_PER_PRODUCT:
            raise CommandError(
                f"--images-per-product must be between {MIN_IMAGES_PER_PRODUCT} and {MAX_IMAGES_PER_PRODUCT}"
            )

        self.stdout.write(f"Downloading Kaggle dataset: {dataset_id}")
        dataset_root = _download_dataset(dataset_id)
        items = _iter_dataset_items(dataset_root)

        if not items:
            raise CommandError(f"no car images found in {dataset_root}")

        if should_shuffle:
            random.shuffle(items)

        self.stdout.write("Clearing previous demo rows...")
        _clear_demo_data()

        categories: dict[str, Category] = {}
        created_products = 0
        created_images = 0
        unindexed_images = 0

        grouped_items: dict[str, list[DatasetItem]] = {}
        for item in items:
            grouped_items.setdefault(item.category, []).append(item)

        for category_label, category_items in grouped_items.items():
            category_name = f"{DEMO_PREFIX} {category_label}"
            category = categories.get(category_name)
            if category is None:
                category = Category.objects.create(name=category_name)
                categories[category_name] = category

            for chunk_index, chunk in enumerate(_chunked(category_items, images_per_product), start=1):
                product = Product.objects.create(
                    name=f"{category_label} #{chunk_index}",
                    description=(
                        f"Car listing generated from the Kaggle Stanford car dataset class {category_label}."
                    ),
                    price=Decimal("24999.00") + Decimal(created_products * 250),
                    category=category,
                )

                for image_idx, item in enumerate(chunk, start=1):
                    image = ProductImage.objects.create(
                        product=product,
                        image=_to_uploaded_file(
                            item.image_path,
                            name=f"{category_label}_{chunk_index}_{image_idx}",
                        ),
                        is_primary=image_idx == 1,
                    )
                    image.refresh_from_db()
                    if not image.indexed or not image.qdrant_id:
                        unindexed_images += 1
                    created_images += 1

                created_products += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {created_products} products, and {created_images} images from {dataset_root}."
            )
        )
        if unindexed_images:
            self.stdout.write(
                self.style.WARNING(
                    f"{unindexed_images} images were not indexed because the search service was unavailable."
                )
            )
