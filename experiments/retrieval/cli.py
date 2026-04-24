from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .config import ExperimentRunConfig, ManifestPaths, SplitConfig
from .manifest import build_manifest


def command_build_manifest(args: argparse.Namespace) -> None:
    summary = build_manifest(
        dataset_cache_dir=Path(args.dataset_cache_dir) if args.dataset_cache_dir else None,
        output_csv=Path(args.output_csv) if args.output_csv else None,
        split_config=SplitConfig(
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            random_seed=args.seed,
            query_images_per_product=args.query_images_per_product,
        ),
    )
    for key, value in summary.items():
        print(f"{key}: {value}")


def command_run_model(args: argparse.Namespace) -> None:
    from .pipeline import run_experiment

    config = ExperimentRunConfig(
        model_id=args.model_id,
        stage=args.stage,
        split=args.split,
        output_dir=Path(args.output_dir),
        manifest_csv=Path(args.manifest_csv),
    )
    summary = run_experiment(config)
    for key, value in summary.items():
        print(f"{key}: {value}")


def command_compare(args: argparse.Namespace) -> None:
    from .pipeline import run_experiment

    model_ids = args.model_ids or [
        "clip_vit_b32_pretrained",
        "dinov2_base_pretrained",
        "dinov2_base_transfer",
        "dinov2_base_finetuned",
    ]
    summaries = []
    for model_id in model_ids:
        config = ExperimentRunConfig(
            model_id=model_id,
            stage="pretrained",
            split=args.split,
            output_dir=Path(args.output_dir),
            manifest_csv=Path(args.manifest_csv),
        )
        summaries.append(run_experiment(config))

    target = Path(args.output_dir) / "comparison_summary.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for summary in summaries:
        for key in summary.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)
    print(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline retrieval experiments for UT Zappos50K.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("build-manifest")
    manifest_parser.add_argument("--dataset-cache-dir", default=str(ManifestPaths().dataset_cache_dir))
    manifest_parser.add_argument("--output-csv", default=str(ManifestPaths().manifest_csv))
    manifest_parser.add_argument("--train-ratio", type=float, default=0.70)
    manifest_parser.add_argument("--val-ratio", type=float, default=0.15)
    manifest_parser.add_argument("--test-ratio", type=float, default=0.15)
    manifest_parser.add_argument("--seed", type=int, default=7)
    manifest_parser.add_argument("--query-images-per-product", type=int, default=1)
    manifest_parser.set_defaults(func=command_build_manifest)

    run_parser = subparsers.add_parser("run-model")
    run_parser.add_argument("--model-id", required=True)
    run_parser.add_argument("--stage", default="pretrained")
    run_parser.add_argument("--split", default="test")
    run_parser.add_argument("--manifest-csv", default=str(ManifestPaths().manifest_csv))
    run_parser.add_argument("--output-dir", default=str(Path("experiments") / "artifacts" / "runs"))
    run_parser.set_defaults(func=command_run_model)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--model-ids", nargs="*")
    compare_parser.add_argument("--split", default="test")
    compare_parser.add_argument("--manifest-csv", default=str(ManifestPaths().manifest_csv))
    compare_parser.add_argument("--output-dir", default=str(Path("experiments") / "artifacts" / "runs"))
    compare_parser.set_defaults(func=command_compare)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
