# Retrieval Model Comparison

This directory contains an offline experiment pipeline for comparing:

- `clip_vit_b32_pretrained`
- `dinov2_base_pretrained`
- `dinov2_base_transfer`
- `dinov2_base_finetuned`

The pipeline is intentionally separate from the Django app runtime. It reuses the live `search_service` image quality and preprocessing logic so offline metrics stay aligned with the deployed retrieval behavior.

## Dataset

The scripts expect the UT Zappos50K cache already present at:

- `main_service/.demo_dataset_cache/ut-zap50k-data`
- `main_service/.demo_dataset_cache/ut-zap50k-images`

## Environment

Run these scripts from the repo root with a Python environment that has the `search_service` dependencies installed:

```bash
python -m pip install -r search_service/requirements.txt
```

## Commands

Build the manifest:

```bash
python -m experiments.retrieval.cli build-manifest
```

Run one model:

```bash
python -m experiments.retrieval.cli run-model --model-id clip_vit_b32_pretrained
```

Run the full comparison:

```bash
python -m experiments.retrieval.cli compare
```

## Output

Artifacts are written under `experiments/artifacts/runs/<model_id>/`:

- `summary.json`
- `metrics_summary.csv`
- `per_query_results.csv`
- `training_history.csv` for trained DINOv2 variants
- `checkpoints/<model_id>_best.pt` for trained DINOv2 variants

The combined compare command also writes:

- `experiments/artifacts/runs/comparison_summary.csv`

## Notes

- Split assignment is by `product_id`, not by image.
- Validation/test queries are only created for products with at least two images.
- Product-level and subcategory-level metrics are both computed.
- The transfer-learning and fine-tuning variants use DINOv2 with a trainable projection head and batch-hard triplet loss.
- If you trained a model in Colab, export either:
  - a Hugging Face-style folder with `save_pretrained(...)`, then set `DINOv2_FINETUNED_SOURCE` or `CLIP_VIT_B32_SOURCE` to that local path, or
  - a PyTorch checkpoint, then set `DINOv2_FINETUNED_CHECKPOINT_PATH` / `DINOv2_TRANSFER_CHECKPOINT_PATH` / `CLIP_VIT_B32_CHECKPOINT_PATH` before starting Docker.
