from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import random
import re

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand, CommandError, call_command

from apps.products.models import Category, Product, ProductImage


DEMO_PREFIX = "Kaggle Cars"
DEFAULT_PRODUCT_TARGET = 24
DEFAULT_DATASET_ID = "jutrera/stanford-car-dataset-by-classes-folder"


@dataclass(frozen=True)
class DatasetItem:
    category: str
    image_path: Path


def _slugish_name(value: str) -> str:
    value = re.sub(r"[_-]+", " ", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value.title()


def _import_kagglehub():
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
    for category_dir in sorted(p for p in dataset_root.iterdir() if p.is_dir()):
        category = _slugish_name(category_dir.name)
        for image_path in sorted(category_dir.rglob("*")):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            items.append(DatasetItem(category=category, image_path=image_path))
    return items


def _clear_demo_data() -> None:
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
            "--products",
            type=int,
            default=DEFAULT_PRODUCT_TARGET,
            help="Number of products to seed.",
        )
        parser.add_argument(
            "--shuffle",
            action="store_true",
            help="Shuffle dataset items before seeding.",
        )

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        target_products = options["products"]
        dataset_id = options["dataset_id"]
        should_shuffle = options["shuffle"]

        if target_products < 1:
            raise CommandError("--products must be >= 1")

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

        for item in items:
            if created_products >= target_products:
                break

            category_name = f"{DEMO_PREFIX} {item.category}"
            category = categories.get(category_name)
            if category is None:
                category = Category.objects.create(name=category_name)
                categories[category_name] = category

            product_name = f"{item.category} #{created_products + 1}"
            product = Product.objects.create(
                name=product_name,
                description=f"Car listing generated from the Kaggle Stanford car dataset class {item.category}.",
                price=Decimal("24999.00") + Decimal(created_products * 250),
                category=category,
            )

            image = ProductImage.objects.create(
                product=product,
                image=_to_uploaded_file(item.image_path, name=f"{item.category}_{created_products + 1}"),
                is_primary=True,
            )
            image.refresh_from_db()

            if not image.indexed or not image.qdrant_id:
                product.delete()
                image.delete()
                continue

            created_products += 1
            created_images += 1

        if created_products < target_products:
            raise CommandError(
                f"seeded only {created_products} products from {dataset_root}; target was {target_products}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {created_products} products, and {created_images} images from {dataset_root}."
            )
        )
