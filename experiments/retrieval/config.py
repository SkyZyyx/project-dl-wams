from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .bootstrap import REPO_ROOT


@dataclass(frozen=True)
class ManifestPaths:
    dataset_cache_dir: Path = REPO_ROOT / "main_service" / ".demo_dataset_cache"
    manifest_csv: Path = REPO_ROOT / "experiments" / "artifacts" / "manifests" / "ut_zappos50k_manifest.csv"


@dataclass(frozen=True)
class SplitConfig:
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    random_seed: int = 7
    query_images_per_product: int = 1

    def validate(self) -> None:
        total = self.train_ratio + self.val_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError("split ratios must sum to 1.0")
        if self.query_images_per_product < 1:
            raise ValueError("query_images_per_product must be >= 1")


@dataclass(frozen=True)
class EvalConfig:
    top_ks: tuple[int, ...] = (1, 5, 10)
    label_levels: tuple[str, ...] = ("product", "subcategory")
    batch_size: int = 16
    num_workers: int = 0
    device: str | None = None


@dataclass(frozen=True)
class TrainConfig:
    epochs: int = 10
    batch_products: int = 8
    images_per_product: int = 2
    projection_dim: int = 256
    learning_rate_head: float = 1e-3
    learning_rate_backbone: float = 1e-5
    weight_decay: float = 1e-4
    triplet_margin: float = 0.2
    early_stopping_patience: int = 3
    max_train_steps_per_epoch: int = 200
    num_workers: int = 0
    device: str | None = None


@dataclass(frozen=True)
class ExperimentRunConfig:
    model_id: str
    stage: str
    split: str = "test"
    output_dir: Path = REPO_ROOT / "experiments" / "artifacts" / "runs"
    manifest_csv: Path = ManifestPaths().manifest_csv
    eval: EvalConfig = field(default_factory=EvalConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
