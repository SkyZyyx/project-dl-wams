from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from dataclasses import asdict
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Iterable

import torch
from PIL import Image
from torch.utils.data import Dataset

from .bootstrap import bootstrap_search_service_django
from .config import EvalConfig, ExperimentRunConfig, TrainConfig
from .dataset import ManifestRow, read_manifest
from .metrics import RankedResult, average_precision_at_k, cosine_similarity, ndcg_at_k, recall_at_k, summarize_metric
from .models import BaseRetrievalModel, create_model, get_experiment_model_spec, load_checkpoint, resolve_device


@lru_cache(maxsize=1)
def _load_search_service_functions():
    bootstrap_search_service_django()
    from apps.search.services.preprocess import preprocess_image_bytes
    from apps.search.services.quality import validate_image_quality

    return preprocess_image_bytes, validate_image_quality


def load_image_bytes_with_runtime_preprocessing(image_path: str) -> bytes:
    preprocess_image_bytes, validate_image_quality = _load_search_service_functions()
    raw_bytes = Path(image_path).read_bytes()
    ok, reason = validate_image_quality(raw_bytes)
    if not ok:
        raise ValueError(f"{image_path}: {reason}")
    return preprocess_image_bytes(raw_bytes)


def _load_pil_from_path(image_path: str) -> Image.Image:
    processed = load_image_bytes_with_runtime_preprocessing(image_path)
    return Image.open(BytesIO(processed)).convert("RGB")


def _batch_rows(rows: list[ManifestRow], batch_size: int) -> Iterable[list[ManifestRow]]:
    for start in range(0, len(rows), batch_size):
        yield rows[start:start + batch_size]


@torch.inference_mode()
def embed_manifest_rows(
    model: BaseRetrievalModel,
    rows: list[ManifestRow],
    *,
    batch_size: int,
    device: torch.device,
) -> tuple[dict[str, list[float]], float]:
    model.eval()
    model.to(device)
    embeddings: dict[str, list[float]] = {}
    start = time.perf_counter()
    for batch in _batch_rows(rows, batch_size):
        images = [_load_pil_from_path(row.image_path) for row in batch]
        vectors = model.encode_pil_images(images).cpu().tolist()
        for row, vector in zip(batch, vectors):
            embeddings[row.cid] = vector
    elapsed = time.perf_counter() - start
    latency_ms = (elapsed / len(rows)) * 1000 if rows else 0.0
    return embeddings, latency_ms


class PKSamplerDataset(Dataset):
    def __init__(self, rows: list[ManifestRow]):
        self.rows = rows
        grouped: dict[str, list[ManifestRow]] = defaultdict(list)
        for row in rows:
            grouped[row.product_id].append(row)
        self.grouped = {key: value for key, value in grouped.items() if len(value) >= 2}
        self.product_ids = sorted(self.grouped.keys())
        if not self.product_ids:
            raise ValueError("training split needs at least one product with >= 2 images")

    def __len__(self) -> int:
        return len(self.product_ids)

    def __getitem__(self, index: int) -> tuple[str, list[ManifestRow]]:
        product_id = self.product_ids[index]
        return product_id, self.grouped[product_id]


def batch_hard_triplet_loss(embeddings: torch.Tensor, labels: torch.Tensor, margin: float) -> torch.Tensor:
    pairwise_distance = 1.0 - torch.matmul(embeddings, embeddings.T)
    same_label = labels.unsqueeze(0) == labels.unsqueeze(1)
    positive_mask = same_label & ~torch.eye(labels.size(0), device=labels.device, dtype=torch.bool)
    negative_mask = ~same_label

    if not positive_mask.any() or not negative_mask.any():
        return torch.zeros((), device=embeddings.device, requires_grad=True)

    hardest_positive = pairwise_distance.masked_fill(~positive_mask, float("-inf")).max(dim=1).values
    hardest_negative = pairwise_distance.masked_fill(~negative_mask, float("inf")).min(dim=1).values
    loss = torch.relu(hardest_positive - hardest_negative + margin)
    valid = positive_mask.any(dim=1) & negative_mask.any(dim=1)
    if valid.any():
        return loss[valid].mean()
    return torch.zeros((), device=embeddings.device, requires_grad=True)


def sample_pk_batch(dataset: PKSamplerDataset, *, batch_products: int, images_per_product: int, step: int) -> tuple[list[Image.Image], torch.Tensor]:
    chosen_products = []
    product_count = len(dataset.product_ids)
    offset = (step * batch_products) % product_count
    for index in range(batch_products):
        chosen_products.append(dataset.product_ids[(offset + index) % product_count])

    images: list[Image.Image] = []
    labels: list[int] = []
    for label_index, product_id in enumerate(chosen_products):
        rows = dataset.grouped[product_id]
        ordered_rows = sorted(rows, key=lambda item: item.cid)
        for image_index in range(images_per_product):
            row = ordered_rows[(step + image_index) % len(ordered_rows)]
            images.append(_load_pil_from_path(row.image_path))
            labels.append(label_index)
    return images, torch.tensor(labels, dtype=torch.long)


def filter_rows(rows: list[ManifestRow], *, split: str, role: str | None = None) -> list[ManifestRow]:
    selected = [row for row in rows if row.split == split]
    if role is not None:
        selected = [row for row in selected if row.role == role]
    return selected


def evaluate_embeddings(
    *,
    manifest_rows: list[ManifestRow],
    embeddings: dict[str, list[float]],
    split: str,
    label_levels: tuple[str, ...],
    top_ks: tuple[int, ...],
) -> tuple[dict[str, float], list[dict[str, object]]]:
    query_rows = filter_rows(manifest_rows, split=split, role="query")
    gallery_rows = filter_rows(manifest_rows, split=split, role="gallery")

    metrics: dict[str, float] = {}
    per_query_rows: list[dict[str, object]] = []

    for label_level in label_levels:
        recall_scores: dict[int, list[float]] = defaultdict(list)
        average_precisions: list[float] = []
        ndcgs: list[float] = []

        for query_row in query_rows:
            query_vector = embeddings.get(query_row.cid)
            if query_vector is None:
                continue

            ranked_results: list[RankedResult] = []
            for gallery_row in gallery_rows:
                gallery_vector = embeddings.get(gallery_row.cid)
                if gallery_vector is None:
                    continue
                if label_level == "product":
                    is_relevant = query_row.product_id == gallery_row.product_id
                else:
                    is_relevant = query_row.subcategory == gallery_row.subcategory
                ranked_results.append(
                    RankedResult(
                        item_id=gallery_row.cid,
                        score=cosine_similarity(query_vector, gallery_vector),
                        is_relevant=is_relevant,
                    )
                )

            ranked_results.sort(key=lambda item: item.score, reverse=True)
            if not any(item.is_relevant for item in ranked_results):
                continue

            metric_row: dict[str, object] = {
                "query_cid": query_row.cid,
                "query_product_id": query_row.product_id,
                "query_subcategory": query_row.subcategory,
                "label_level": label_level,
            }
            for top_k in top_ks:
                recall_value = recall_at_k(ranked_results, top_k)
                recall_scores[top_k].append(recall_value)
                metric_row[f"recall_at_{top_k}"] = recall_value

            ap = average_precision_at_k(ranked_results, max(top_ks))
            ndcg_value = ndcg_at_k(ranked_results, max(top_ks))
            average_precisions.append(ap)
            ndcgs.append(ndcg_value)
            metric_row[f"map_at_{max(top_ks)}"] = ap
            metric_row[f"ndcg_at_{max(top_ks)}"] = ndcg_value
            metric_row["top_result_cid"] = ranked_results[0].item_id if ranked_results else ""
            metric_row["top_result_score"] = ranked_results[0].score if ranked_results else 0.0
            per_query_rows.append(metric_row)

        for top_k in top_ks:
            metrics[f"recall_at_{top_k}_{label_level}"] = summarize_metric(recall_scores[top_k])
        metrics[f"map_at_{max(top_ks)}_{label_level}"] = summarize_metric(average_precisions)
        metrics[f"ndcg_at_{max(top_ks)}_{label_level}"] = summarize_metric(ndcgs)

    return metrics, per_query_rows


def train_model(
    model: BaseRetrievalModel,
    train_rows: list[ManifestRow],
    val_rows: list[ManifestRow],
    train_config: TrainConfig,
    eval_config: EvalConfig,
    output_dir: Path,
) -> tuple[Path, list[dict[str, object]], dict[str, float]]:
    device = resolve_device(train_config.device)
    model.to(device)
    model.train()

    head_params = [parameter for name, parameter in model.named_parameters() if parameter.requires_grad and "encoder" not in name]
    backbone_params = [parameter for name, parameter in model.named_parameters() if parameter.requires_grad and "encoder" in name]

    parameter_groups = []
    if head_params:
        parameter_groups.append({"params": head_params, "lr": train_config.learning_rate_head})
    if backbone_params:
        parameter_groups.append({"params": backbone_params, "lr": train_config.learning_rate_backbone})
    optimizer = torch.optim.AdamW(parameter_groups, weight_decay=train_config.weight_decay)

    dataset = PKSamplerDataset(train_rows)
    history: list[dict[str, object]] = []
    best_metric = float("-inf")
    best_checkpoint = output_dir / "checkpoints" / f"{model.spec.model_id}_best.pt"
    best_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    epochs_without_improvement = 0

    for epoch in range(1, train_config.epochs + 1):
        epoch_losses: list[float] = []
        for step in range(train_config.max_train_steps_per_epoch):
            images, labels = sample_pk_batch(
                dataset,
                batch_products=train_config.batch_products,
                images_per_product=train_config.images_per_product,
                step=step,
            )
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            embeddings = model.encode_pil_images(images)
            loss = batch_hard_triplet_loss(embeddings, labels, margin=train_config.triplet_margin)
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu().item()))

        val_embeddings, _ = embed_manifest_rows(model, val_rows, batch_size=eval_config.batch_size, device=device)
        val_metrics, _ = evaluate_embeddings(
            manifest_rows=val_rows,
            embeddings=val_embeddings,
            split="val",
            label_levels=eval_config.label_levels,
            top_ks=eval_config.top_ks,
        )
        selection_metric = val_metrics.get("recall_at_10_product", 0.0)
        history_row = {
            "epoch": epoch,
            "train_loss": sum(epoch_losses) / len(epoch_losses),
            "val_recall_at_10_product": selection_metric,
        }
        history_row.update(val_metrics)
        history.append(history_row)

        if selection_metric > best_metric:
            best_metric = selection_metric
            epochs_without_improvement = 0
            torch.save(
                {
                    "model_id": model.spec.model_id,
                    "model_state_dict": model.state_dict(),
                    "train_config": asdict(train_config),
                    "val_metrics": val_metrics,
                },
                best_checkpoint,
            )
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= train_config.early_stopping_patience:
                break

    load_checkpoint(model, best_checkpoint)
    return best_checkpoint, history, {"best_val_recall_at_10_product": best_metric}


def save_csv(rows: list[dict[str, object]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_summary(summary: dict[str, object], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def run_experiment(config: ExperimentRunConfig) -> dict[str, object]:
    manifest_rows = read_manifest(config.manifest_csv)
    spec = get_experiment_model_spec(config.model_id)
    model = create_model(config.model_id, projection_dim=config.train.projection_dim)
    output_dir = config.output_dir / config.model_id
    output_dir.mkdir(parents=True, exist_ok=True)

    train_history: list[dict[str, object]] = []
    checkpoint_path: Path | None = None
    train_summary: dict[str, float] = {}
    if spec.stage in {"transfer", "finetuned"}:
        train_rows = filter_rows(manifest_rows, split="train")
        val_rows = [row for row in manifest_rows if row.split == "val"]
        checkpoint_path, train_history, train_summary = train_model(
            model,
            train_rows=train_rows,
            val_rows=val_rows,
            train_config=config.train,
            eval_config=config.eval,
            output_dir=output_dir,
        )

    device = resolve_device(config.eval.device or config.train.device)
    split_rows = [row for row in manifest_rows if row.split == config.split]
    embeddings, latency_ms = embed_manifest_rows(model, split_rows, batch_size=config.eval.batch_size, device=device)
    metrics, per_query_rows = evaluate_embeddings(
        manifest_rows=manifest_rows,
        embeddings=embeddings,
        split=config.split,
        label_levels=config.eval.label_levels,
        top_ks=config.eval.top_ks,
    )

    summary: dict[str, object] = {
        "model_name": spec.label,
        "model_id": spec.model_id,
        "training_stage": spec.stage,
        "embedding_dim": model.embedding_dim,
        "num_params": model.get_parameter_count(),
        "trainable_params": model.get_trainable_parameter_count(),
        "embed_latency_ms": latency_ms,
        "index_time_sec": 0.0,
        "checkpoint_path": str(checkpoint_path) if checkpoint_path else "",
    }
    summary.update(metrics)
    summary.update(train_summary)

    save_summary(summary, output_dir / "summary.json")
    save_csv([summary], output_dir / "metrics_summary.csv")
    if train_history:
        save_csv(train_history, output_dir / "training_history.csv")
    if per_query_rows:
        save_csv(per_query_rows, output_dir / "per_query_results.csv")
    return summary
