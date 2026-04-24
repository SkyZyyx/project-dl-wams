from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .config import ManifestPaths, SplitConfig
from .dataset import build_manifest_rows, discover_dataset_records, write_manifest


def build_manifest(
    *,
    dataset_cache_dir: Path | None = None,
    output_csv: Path | None = None,
    split_config: SplitConfig | None = None,
) -> dict[str, object]:
    paths = ManifestPaths(
        dataset_cache_dir=dataset_cache_dir or ManifestPaths().dataset_cache_dir,
        manifest_csv=output_csv or ManifestPaths().manifest_csv,
    )
    config = split_config or SplitConfig()
    records = discover_dataset_records(paths)
    rows = build_manifest_rows(records, config)
    write_manifest(rows, paths.manifest_csv)

    split_counts = Counter(row.split for row in rows)
    role_counts = Counter(row.role for row in rows)
    product_counts = Counter(row.product_id for row in rows)
    query_products = sum(1 for product_id, count in product_counts.items() if count >= 2)

    return {
        "manifest_csv": str(paths.manifest_csv),
        "records": len(records),
        "rows": len(rows),
        "split_counts": dict(split_counts),
        "role_counts": dict(role_counts),
        "products_with_multiple_images": query_products,
        "split_config": asdict(config),
    }
