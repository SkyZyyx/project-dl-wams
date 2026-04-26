from __future__ import annotations

from pathlib import Path
import re

import torch
from PIL import Image
from torch import nn
from transformers import AutoImageProcessor, AutoModel, AutoProcessor, CLIPVisionModelWithProjection


def l2_normalize(tensor: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.normalize(tensor, p=2, dim=1)


def _load_checkpoint(path: str | None) -> dict[str, object] | None:
    if not path:
        return None

    checkpoint_path = Path(path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint_path}")
    if checkpoint_path.is_dir():
        raise ValueError(f"checkpoint path must be a file, not a directory: {checkpoint_path}")

    loaded = torch.load(checkpoint_path, map_location="cpu")
    if isinstance(loaded, dict):
        return loaded
    return {"state_dict": loaded}


def _extract_state_dict(checkpoint: dict[str, object]) -> dict[str, object]:
    for key in ("model_state_dict", "state_dict", "model"):
        value = checkpoint.get(key)
        if isinstance(value, dict):
            return value
    return {key: value for key, value in checkpoint.items() if isinstance(value, torch.Tensor)}


def _state_dict_has_triplet_signature(state_dict: dict[str, object]) -> bool:
    has_backbone = any(key.startswith("backbone.") for key in state_dict)
    has_projection = any(key.startswith("projection.") for key in state_dict)
    return has_backbone and has_projection


def _infer_triplet_projection_dim(state_dict: dict[str, object], fallback_dim: int) -> int:
    weight = state_dict.get("projection.4.weight")
    if isinstance(weight, torch.Tensor) and weight.ndim == 2 and weight.shape[0] > 0:
        return int(weight.shape[0])
    weight = state_dict.get("projection.1.weight")
    if isinstance(weight, torch.Tensor) and weight.ndim == 2 and weight.shape[0] > 0:
        return int(weight.shape[0])
    return fallback_dim


def _infer_triplet_image_size(state_dict: dict[str, object], source: str, fallback_size: int = 224) -> int:
    pos_embed = state_dict.get("backbone.pos_embed")
    if isinstance(pos_embed, torch.Tensor) and pos_embed.ndim == 3 and pos_embed.shape[1] > 1:
        token_count = int(pos_embed.shape[1] - 1)
        grid = int(token_count**0.5)
        if grid * grid == token_count:
            patch = 14
            match = re.search(r"patch(\d+)", source or "")
            if match:
                try:
                    patch = int(match.group(1))
                except ValueError:
                    patch = 14
            return grid * patch
    return fallback_size


def _load_state_dict_flexibly(module: nn.Module, state_dict: dict[str, object]) -> None:
    incompatible = module.load_state_dict(state_dict, strict=False)
    if not incompatible.missing_keys and not incompatible.unexpected_keys:
        return

    if hasattr(module, "encoder"):
        encoder = getattr(module, "encoder")
        if isinstance(encoder, nn.Module):
            encoder_incompatible = encoder.load_state_dict(state_dict, strict=False)
            if not encoder_incompatible.missing_keys and not encoder_incompatible.unexpected_keys:
                return

    raise ValueError("checkpoint does not match the requested model architecture")


class ClipNotebookEmbedder(nn.Module):
    def __init__(self, source: str, checkpoint_path: str | None = None):
        super().__init__()
        self.processor = AutoProcessor.from_pretrained(source)
        self.encoder = CLIPVisionModelWithProjection.from_pretrained(source)
        checkpoint = _load_checkpoint(checkpoint_path)
        if checkpoint is not None:
            _load_state_dict_flexibly(self, _extract_state_dict(checkpoint))

    def forward(self, **inputs):
        return self.encoder(**inputs)

    def encode_pil_images(self, images: list[Image.Image]) -> torch.Tensor:
        inputs = self.processor(images=images, return_tensors="pt")
        device = next(self.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        outputs = self.encoder(**inputs)
        return l2_normalize(outputs.image_embeds)


class DinoNotebookEmbedder(nn.Module):
    def __init__(self, source: str, state_dict: dict[str, object] | None = None, *, projection_dim: int | None = None):
        super().__init__()
        self.processor = AutoImageProcessor.from_pretrained(source)
        self.encoder = AutoModel.from_pretrained(source)
        hidden_size = int(self.encoder.config.hidden_size)
        head_output_dim = projection_dim or hidden_size
        self.projection = nn.Identity() if head_output_dim == hidden_size else nn.Linear(hidden_size, head_output_dim)
        if state_dict is not None:
            _load_state_dict_flexibly(self, state_dict)

    def forward(self, **inputs):
        return self.encoder(**inputs)

    def encode_pil_images(self, images: list[Image.Image]) -> torch.Tensor:
        inputs = self.processor(images=images, return_tensors="pt")
        device = next(self.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        outputs = self.encoder(**inputs)
        pooled = outputs.last_hidden_state[:, 0, :]
        projected = self.projection(pooled)
        return l2_normalize(projected)


class DinoTripletNotebookEmbedder(nn.Module):
    def __init__(
        self,
        source: str,
        *,
        state_dict: dict[str, object],
        projection_dim: int = 512,
        dropout: float = 0.2,
    ):
        super().__init__()
        try:
            import timm
            from timm.data import create_transform, resolve_model_data_config
        except Exception as exc:  # pragma: no cover - defensive for missing dependency
            raise RuntimeError("timm is required to load triplet fine-tuned DINO checkpoints") from exc

        model_name = source or "vit_base_patch14_dinov2.lvd142m"
        inferred_image_size = _infer_triplet_image_size(state_dict, model_name, fallback_size=224)
        try:
            self.backbone = timm.create_model(
                model_name,
                pretrained=True,
                num_classes=0,
                img_size=inferred_image_size,
            )
        except TypeError:
            self.backbone = timm.create_model(model_name, pretrained=True, num_classes=0)

        feature_dim = int(getattr(self.backbone, "num_features"))
        self.projection = nn.Sequential(
            nn.LayerNorm(feature_dim),
            nn.Linear(feature_dim, projection_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(projection_dim, projection_dim),
        )
        _load_state_dict_flexibly(self, state_dict)

        data_config = resolve_model_data_config(self.backbone)
        data_config["input_size"] = (3, inferred_image_size, inferred_image_size)
        self._transform = create_transform(**data_config, is_training=False)
        self.processor = None

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        features = self.backbone(pixel_values)
        projected = self.projection(features)
        return l2_normalize(projected)

    def encode_pil_images(self, images: list[Image.Image]) -> torch.Tensor:
        tensors = [self._transform(image.convert("RGB")) for image in images]
        batch = torch.stack(tensors, dim=0)
        device = next(self.parameters()).device
        return self.forward(batch.to(device))


def create_dino_embedder(
    source: str,
    checkpoint_path: str | None,
    *,
    projection_dim: int | None = None,
) -> nn.Module:
    checkpoint = _load_checkpoint(checkpoint_path)
    state_dict = _extract_state_dict(checkpoint) if checkpoint is not None else None

    if state_dict and _state_dict_has_triplet_signature(state_dict):
        inferred_dim = _infer_triplet_projection_dim(state_dict, projection_dim or 512)
        return DinoTripletNotebookEmbedder(
            source=source,
            state_dict=state_dict,
            projection_dim=inferred_dim,
        )

    return DinoNotebookEmbedder(source=source, state_dict=state_dict, projection_dim=projection_dim)
