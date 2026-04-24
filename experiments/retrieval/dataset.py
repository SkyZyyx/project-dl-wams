from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import ManifestPaths, SplitConfig


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class DatasetRecord:
    cid: str
    product_id: str
    category: str
    subcategory: str
    brand: str
    image_path: Path


@dataclass(frozen=True)
class ManifestRow:
    image_path: str
    cid: str
    product_id: str
    category: str
    subcategory: str
    brand: str
    split: str
    role: str


def _find_first_file(root: Path, filename: str) -> Path:
    matches = list(root.rglob(filename))
    if not matches:
        raise FileNotFoundError(f"could not find {filename} inside {root}")
    return matches[0]


def _load_metadata(meta_csv: Path) -> list[dict[str, str]]:
    with meta_csv.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_image_index(images_root: Path) -> dict[str, Path]:
    image_index: dict[str, Path] = {}
    for path in images_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        image_index.setdefault(path.stem.lower(), path)
    return image_index


def _lookup_image_path(image_index: dict[str, Path], cid: str) -> Path | None:
    cid_key = cid.lower()
    exact = image_index.get(cid_key)
    if exact is not None:
        return exact

    cid_with_dots = cid_key.replace("-", ".")
    exact_dot = image_index.get(cid_with_dots)
    if exact_dot is not None:
        return exact_dot

    for key, path in image_index.items():
        if key.startswith(cid_key):
            return path
    return None


def _stable_fraction(text: str, *, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big") / float(2**64)


def _assign_split(product_id: str, split_config: SplitConfig) -> str:
    split_config.validate()
    value = _stable_fraction(product_id, seed=split_config.random_seed)
    if value < split_config.train_ratio:
        return "train"
    if value < split_config.train_ratio + split_config.val_ratio:
        return "val"
    return "test"


def discover_dataset_records(paths: ManifestPaths | None = None) -> list[DatasetRecord]:
    resolved_paths = paths or ManifestPaths()
    data_root = resolved_paths.dataset_cache_dir / "ut-zap50k-data"
    images_root = resolved_paths.dataset_cache_dir / "ut-zap50k-images"

    meta_csv = _find_first_file(data_root, "meta-data.csv")
    rows = _load_metadata(meta_csv)
    image_index = _build_image_index(images_root)

    discovered: list[DatasetRecord] = []
    seen_cids: set[str] = set()

    for row in rows:
        cid = (row.get("CID") or "").strip()
        category = (row.get("Category") or "").strip()
        subcategory = (row.get("SubCategory") or "").strip() or category

        if not cid or not category:
            continue
        cid_key = cid.lower()
        if cid_key in seen_cids:
            continue

        image_path = _lookup_image_path(image_index, cid)
        if image_path is None:
            continue

        brand = image_path.parent.name.strip() or "Unknown"
        discovered.append(
            DatasetRecord(
                cid=cid,
                product_id=cid.split("-")[0],
                category=category,
                subcategory=subcategory,
                brand=brand,
                image_path=image_path.resolve(),
            )
        )
        seen_cids.add(cid_key)

    if not discovered:
        raise RuntimeError("no UT Zappos50K records with usable images were discovered")
    return discovered


def build_manifest_rows(
    records: Iterable[DatasetRecord],
    split_config: SplitConfig | None = None,
) -> list[ManifestRow]:
    config = split_config or SplitConfig()
    grouped: dict[str, list[DatasetRecord]] = defaultdict(list)
    for record in records:
        grouped[record.product_id].append(record)

    rows: list[ManifestRow] = []
    for product_id, product_records in sorted(grouped.items()):
        ordered_records = sorted(product_records, key=lambda item: item.cid)
        split = _assign_split(product_id, config)
        query_count = config.query_images_per_product if split in {"val", "test"} and len(ordered_records) >= 2 else 0

        for index, record in enumerate(ordered_records):
            role = "train"
            if split in {"val", "test"}:
                role = "query" if index < query_count else "gallery"

            rows.append(
                ManifestRow(
                    image_path=str(record.image_path),
                    cid=record.cid,
                    product_id=record.product_id,
                    category=record.category,
                    subcategory=record.subcategory,
                    brand=record.brand,
                    split=split,
                    role=role,
                )
            )
    return rows


def write_manifest(rows: Iterable[ManifestRow], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image_path",
        "cid",
        "product_id",
        "category",
        "subcategory",
        "brand",
        "split",
        "role",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
    return target


def read_manifest(path: Path) -> list[ManifestRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [ManifestRow(**row) for row in csv.DictReader(handle)]
