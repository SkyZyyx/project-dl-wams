from __future__ import annotations

import csv
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand, CommandError, call_command

from apps.products.models import Category, Product, ProductImage


DEMO_PREFIX = "UT-Zap50K"
DATASET_BASE_URL = "https://vision.cs.utexas.edu/projects/finegrained/utzap50k"
DATASET_ARCHIVES = {
    "data": f"{DATASET_BASE_URL}/ut-zap50k-data.zip",
    "images": f"{DATASET_BASE_URL}/ut-zap50k-images.zip",
}

DEFAULT_PRODUCT_TARGET = 8
MAX_IMAGES_PER_PRODUCT = 3


@dataclass(frozen=True)
class DemoRecord:
    cid: str
    category: str
    subcategory: str
    product_id: str
    image_path: Path


def _download_file(url: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target

    with urlopen(url, timeout=120) as response:
        target.write_bytes(response.read())
    return target


def _extract_zip(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / ".extracted"
    if marker.exists():
        return destination

    with zipfile.ZipFile(archive) as zf:
        zf.extractall(destination)

    marker.write_text("ok", encoding="utf-8")
    return destination


def _find_first_file(root: Path, filename: str) -> Path:
    matches = list(root.rglob(filename))
    if not matches:
        raise CommandError(f"could not find {filename} inside {root}")
    return matches[0]


def _load_metadata(meta_csv: Path) -> list[dict[str, str]]:
    with meta_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def _build_image_index(images_root: Path) -> dict[str, Path]:
    image_index: dict[str, Path] = {}
    for path in images_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        key = path.stem.lower()
        image_index.setdefault(key, path)
    return image_index


def _lookup_image_path(image_index: dict[str, Path], cid: str) -> Path | None:
    cid_key = cid.lower()
    exact = image_index.get(cid_key)
    if exact is not None:
        return exact

    # UT Zappos50K uses dashes in CIDs but dots in filenames (e.g., 100627-72 -> 100627.72)
    cid_with_dots = cid_key.replace("-", ".")
    exact_dot = image_index.get(cid_with_dots)
    if exact_dot is not None:
        return exact_dot

    for key, path in image_index.items():
        if key.startswith(cid_key):
            return path

    return None


def _ordered_product_groups(grouped: dict[str, list[DemoRecord]]) -> list[list[DemoRecord]]:
    per_category_products: dict[str, dict[str, list[DemoRecord]]] = {}
    category_order = sorted(grouped.keys())

    for category in category_order:
        per_product: dict[str, list[DemoRecord]] = defaultdict(list)
        for record in grouped[category]:
            per_product[record.product_id].append(record)
        per_category_products[category] = per_product

    ordered_product_keys: list[tuple[str, str]] = []
    category_indexes = {category: 0 for category in category_order}
    category_product_ids = {
        category: sorted(per_category_products[category].keys()) for category in category_order
    }

    while True:
        progressed = False
        for category in category_order:
            product_ids = category_product_ids[category]
            index = category_indexes[category]
            if index >= len(product_ids):
                continue
            ordered_product_keys.append((category, product_ids[index]))
            category_indexes[category] += 1
            progressed = True
        if not progressed:
            break

    return [
        sorted(per_category_products[category][product_id], key=lambda item: item.cid)
        for category, product_id in ordered_product_keys
    ]


def _seed_product_groups() -> list[list[DemoRecord]]:
    cache_dir = Path(settings.MEDIA_ROOT).resolve().parent / ".demo_dataset_cache"
    data_zip = _download_file(DATASET_ARCHIVES["data"], cache_dir / "ut-zap50k-data.zip")
    images_zip = _download_file(DATASET_ARCHIVES["images"], cache_dir / "ut-zap50k-images.zip")

    data_root = _extract_zip(data_zip, cache_dir / "ut-zap50k-data")
    images_root = _extract_zip(images_zip, cache_dir / "ut-zap50k-images")

    meta_csv = _find_first_file(data_root, "meta-data.csv")
    rows = _load_metadata(meta_csv)
    image_index = _build_image_index(images_root)

    grouped: dict[str, list[DemoRecord]] = defaultdict(list)
    seen_cids: set[str] = set()

    for row in rows:
        cid = (row.get("CID") or row.get("cid") or "").strip()
        category = (row.get("Category") or row.get("category") or "").strip()
        subcategory = (row.get("SubCategory") or row.get("subcategory") or "").strip()

        if not cid or not category:
            continue

        cid_key = cid.lower()
        if cid_key in seen_cids:
            continue

        image_path = _lookup_image_path(image_index, cid)
        if image_path is None:
            continue

        product_id = cid.split("-")[0]
        grouped[category].append(
            DemoRecord(
                cid=cid,
                category=category,
                subcategory=subcategory or category,
                product_id=product_id,
                image_path=image_path,
            )
        )
        seen_cids.add(cid_key)

    selected = _ordered_product_groups(grouped)

    if not selected:
        raise CommandError("no UT Zappos50K images were found after download")

    return selected


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
    help = "Seed demo products from the UT Zappos50K shoe dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--products",
            type=int,
            default=DEFAULT_PRODUCT_TARGET,
            help="Number of products to seed across categories.",
        )
        parser.add_argument(
            "--images-per-product",
            type=int,
            default=MAX_IMAGES_PER_PRODUCT,
            help="Maximum number of images to index per product.",
        )

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        target_products = options["products"]
        max_images_per_product = options["images_per_product"]
        if target_products < 1:
            raise CommandError("--products must be >= 1")
        if max_images_per_product < 1:
            raise CommandError("--images-per-product must be >= 1")

        self.stdout.write("Downloading and preparing UT Zappos50K demo data...")
        product_groups = _seed_product_groups()
        if target_products > len(product_groups):
            raise CommandError(
                f"requested {target_products} demo products but only {len(product_groups)} products have usable images"
            )

        self.stdout.write("Clearing previous demo rows...")
        _clear_demo_data()

        categories: dict[str, Category] = {}
        products: dict[str, Product] = {}
        product_order: list[str] = []
        indexed_image_count = 0

        for records in product_groups:
            if len(product_order) >= target_products:
                break

            record = records[0]
            category_name = f"{DEMO_PREFIX} {record.category}"
            category = categories.get(category_name)
            if category is None:
                category = Category.objects.create(name=category_name)
                categories[category_name] = category

            product_key = f"{record.category}:{record.product_id}"
            product = Product.objects.create(
                name=f"{DEMO_PREFIX} {record.subcategory} {record.product_id}",
                description=f"UT Zappos50K shoe from the {record.category.lower()} category.",
                price=Decimal("49.99"),
                category=category,
            )

            created_images: list[ProductImage] = []
            product_failed = False
            for image_index, product_record in enumerate(records[:max_images_per_product]):
                image = ProductImage.objects.create(
                    product=product,
                    image=_to_uploaded_file(product_record.image_path, name=product_record.cid),
                    is_primary=image_index == 0,
                )
                image.refresh_from_db()

                if not image.indexed or not image.qdrant_id:
                    product_failed = True
                    image.delete()
                    break

                created_images.append(image)

            if product_failed or not created_images:
                product.delete()
                if not category.products.exists():
                    categories.pop(category_name, None)
                    category.delete()
                continue

            products[product_key] = product
            product_order.append(product_key)
            indexed_image_count += len(created_images)

        if len(product_order) < target_products:
            raise CommandError(
                f"seeded only {len(product_order)} products before candidates were exhausted; target was {target_products}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {len(product_order)} products, and {indexed_image_count} images from UT Zappos50K."
            )
        )
