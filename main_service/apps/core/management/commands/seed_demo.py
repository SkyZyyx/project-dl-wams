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

MAX_PRODUCTS_PER_CATEGORY = 2
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

    for key, path in image_index.items():
        if key.startswith(cid_key):
            return path

    return None


def _seed_records() -> list[DemoRecord]:
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

    selected: list[DemoRecord] = []
    for category in sorted(grouped.keys()):
        per_category = grouped[category]
        per_product: dict[str, list[DemoRecord]] = defaultdict(list)
        for record in per_category:
            per_product[record.product_id].append(record)

        for product_id in sorted(per_product.keys())[:MAX_PRODUCTS_PER_CATEGORY]:
            selected.extend(sorted(per_product[product_id], key=lambda item: item.cid)[:MAX_IMAGES_PER_PRODUCT])

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

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        self.stdout.write("Downloading and preparing UT Zappos50K demo data...")
        records = _seed_records()

        self.stdout.write("Clearing previous demo rows...")
        _clear_demo_data()

        categories: dict[str, Category] = {}
        products: dict[str, Product] = {}
        product_order: list[str] = []

        for record in records:
            category_name = f"{DEMO_PREFIX} {record.category}"
            category = categories.get(category_name)
            if category is None:
                category = Category.objects.create(name=category_name)
                categories[category_name] = category

            product_key = f"{record.category}:{record.product_id}"
            product = products.get(product_key)
            if product is None:
                product = Product.objects.create(
                    name=f"{DEMO_PREFIX} {record.subcategory} {record.product_id}",
                    description=f"UT Zappos50K shoe from the {record.category.lower()} category.",
                    price=Decimal("49.99"),
                    category=category,
                )
                products[product_key] = product
                product_order.append(product_key)

            image = ProductImage.objects.create(
                product=product,
                image=_to_uploaded_file(record.image_path, name=record.cid),
                is_primary=not product.images.exists(),
            )
            image.refresh_from_db()

            if not image.indexed or not image.qdrant_id:
                raise CommandError(
                    f"failed to index demo image {record.cid} (indexed={image.indexed}, qdrant_id={image.qdrant_id!r})"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {len(product_order)} products, and {len(records)} images from UT Zappos50K."
            )
        )
