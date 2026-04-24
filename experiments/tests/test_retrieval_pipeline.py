from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.retrieval.config import SplitConfig
from experiments.retrieval.dataset import DatasetRecord, build_manifest_rows, read_manifest, write_manifest
from experiments.retrieval.metrics import RankedResult, average_precision_at_k, ndcg_at_k, recall_at_k


class ManifestBuilderTests(unittest.TestCase):
    def test_build_manifest_rows_assigns_queries_only_to_eval_products_with_multiple_images(self):
        records = [
            DatasetRecord("prod-a-1", "prod-a", "Shoes", "Sneakers", "Nike", Path("/tmp/a1.jpg")),
            DatasetRecord("prod-a-2", "prod-a", "Shoes", "Sneakers", "Nike", Path("/tmp/a2.jpg")),
            DatasetRecord("prod-b-1", "prod-b", "Shoes", "Sneakers", "Nike", Path("/tmp/b1.jpg")),
        ]

        rows = build_manifest_rows(
            records,
            SplitConfig(train_ratio=0.0, val_ratio=1.0, test_ratio=0.0, random_seed=1, query_images_per_product=1),
        )

        prod_a_rows = [row for row in rows if row.product_id == "prod-a"]
        prod_b_rows = [row for row in rows if row.product_id == "prod-b"]
        self.assertEqual([row.role for row in prod_a_rows], ["query", "gallery"])
        self.assertEqual([row.role for row in prod_b_rows], ["gallery"])

    def test_manifest_round_trip(self):
        rows = build_manifest_rows(
            [
                DatasetRecord("prod-a-1", "prod-a", "Shoes", "Sneakers", "Nike", Path("/tmp/a1.jpg")),
                DatasetRecord("prod-a-2", "prod-a", "Shoes", "Sneakers", "Nike", Path("/tmp/a2.jpg")),
            ],
            SplitConfig(train_ratio=0.0, val_ratio=0.0, test_ratio=1.0, random_seed=1, query_images_per_product=1),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.csv"
            write_manifest(rows, manifest_path)
            loaded = read_manifest(manifest_path)
        self.assertEqual(rows, loaded)


class MetricTests(unittest.TestCase):
    def test_recall_average_precision_and_ndcg(self):
        ranked = [
            RankedResult("a", 0.9, False),
            RankedResult("b", 0.8, True),
            RankedResult("c", 0.7, True),
        ]
        self.assertEqual(recall_at_k(ranked, 1), 0.0)
        self.assertEqual(recall_at_k(ranked, 2), 1.0)
        self.assertAlmostEqual(average_precision_at_k(ranked, 3), ((1 / 2) + (2 / 3)) / 2)
        self.assertGreater(ndcg_at_k(ranked, 3), 0.0)


if __name__ == "__main__":
    unittest.main()
