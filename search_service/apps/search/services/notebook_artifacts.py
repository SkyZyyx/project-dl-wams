from __future__ import annotations

from pathlib import Path

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
    def __init__(self, source: str, checkpoint_path: str | None = None, *, projection_dim: int | None = None):
        super().__init__()
        self.processor = AutoImageProcessor.from_pretrained(source)
        self.encoder = AutoModel.from_pretrained(source)
        hidden_size = int(self.encoder.config.hidden_size)
        head_output_dim = projection_dim or hidden_size
        self.projection = nn.Identity() if head_output_dim == hidden_size else nn.Linear(hidden_size, head_output_dim)
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
        pooled = outputs.last_hidden_state[:, 0, :]
        projected = self.projection(pooled)
        return l2_normalize(projected)
