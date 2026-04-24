from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from transformers import AutoImageProcessor, AutoModel, AutoProcessor, CLIPVisionModelWithProjection

from .bootstrap import bootstrap_search_service_django


def resolve_device(device: str | None = None) -> torch.device:
    if device:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def l2_normalize(tensor: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.normalize(tensor, p=2, dim=1)


@dataclass(frozen=True)
class ExperimentModelSpec:
    model_id: str
    label: str
    stage: str
    family: str
    source: str
    embedding_dim: int
    checkpoint_path: str | None = None


TRAINING_STAGE_BY_MODEL_ID = {
    "clip_vit_b32_pretrained": "pretrained",
    "dinov2_base_pretrained": "pretrained",
    "dinov2_base_transfer": "transfer",
    "dinov2_base_finetuned": "finetuned",
}

EMBEDDING_DIM_BY_MODEL_ID = {
    "clip_vit_b32_pretrained": 512,
    "dinov2_base_pretrained": 768,
    "dinov2_base_transfer": 256,
    "dinov2_base_finetuned": 256,
}


@lru_cache(maxsize=1)
def get_experiment_model_specs() -> dict[str, ExperimentModelSpec]:
    bootstrap_search_service_django()
    from apps.search.services.model_registry import get_model_registry

    specs: dict[str, ExperimentModelSpec] = {}
    for model_id, runtime_spec in get_model_registry().items():
        specs[model_id] = ExperimentModelSpec(
            model_id=model_id,
            label=runtime_spec.label,
            stage=TRAINING_STAGE_BY_MODEL_ID[model_id],
            family=runtime_spec.family,
            source=runtime_spec.source,
            embedding_dim=EMBEDDING_DIM_BY_MODEL_ID[model_id],
        )
    return specs


def get_experiment_model_spec(model_id: str) -> ExperimentModelSpec:
    try:
        return get_experiment_model_specs()[model_id]
    except KeyError as exc:
        raise ValueError(f"unknown experiment model id: {model_id}") from exc


class BaseRetrievalModel(nn.Module):
    def __init__(self, spec: ExperimentModelSpec):
        super().__init__()
        self.spec = spec

    @property
    def embedding_dim(self) -> int:
        return self.spec.embedding_dim

    def encode_pil_images(self, images: list[Image.Image]) -> torch.Tensor:
        raise NotImplementedError

    def get_trainable_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad)

    def get_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())


class ClipImageEncoder(BaseRetrievalModel):
    def __init__(self, spec: ExperimentModelSpec):
        super().__init__(spec)
        self.processor = AutoProcessor.from_pretrained(spec.source)
        self.encoder = CLIPVisionModelWithProjection.from_pretrained(spec.source)

    def encode_pil_images(self, images: list[Image.Image]) -> torch.Tensor:
        inputs = self.processor(images=images, return_tensors="pt")
        device = next(self.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        outputs = self.encoder(**inputs)
        return l2_normalize(outputs.image_embeds)


class DinoRetrievalModel(BaseRetrievalModel):
    def __init__(
        self,
        spec: ExperimentModelSpec,
        *,
        projection_dim: int | None = None,
        train_backbone: bool = False,
        unfreeze_last_blocks: int = 0,
    ):
        super().__init__(spec)
        self.processor = AutoImageProcessor.from_pretrained(spec.source)
        self.encoder = AutoModel.from_pretrained(spec.source)
        hidden_size = int(self.encoder.config.hidden_size)
        head_output_dim = projection_dim or hidden_size
        self.projection = nn.Identity() if head_output_dim == hidden_size else nn.Linear(hidden_size, head_output_dim)
        self._configure_trainability(train_backbone=train_backbone, unfreeze_last_blocks=unfreeze_last_blocks)

    def _configure_trainability(self, *, train_backbone: bool, unfreeze_last_blocks: int) -> None:
        for parameter in self.encoder.parameters():
            parameter.requires_grad = False

        if train_backbone:
            if hasattr(self.encoder, "encoder") and hasattr(self.encoder.encoder, "layer"):
                layers = list(self.encoder.encoder.layer)
                for layer in layers[-unfreeze_last_blocks:]:
                    for parameter in layer.parameters():
                        parameter.requires_grad = True
                if hasattr(self.encoder, "layernorm"):
                    for parameter in self.encoder.layernorm.parameters():
                        parameter.requires_grad = True
            else:
                for parameter in self.encoder.parameters():
                    parameter.requires_grad = True

        for parameter in self.projection.parameters():
            parameter.requires_grad = True

    def _forward_features(self, images: list[Image.Image]) -> torch.Tensor:
        inputs = self.processor(images=images, return_tensors="pt")
        device = next(self.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        outputs = self.encoder(**inputs)
        pooled = outputs.last_hidden_state[:, 0, :]
        projected = self.projection(pooled)
        return l2_normalize(projected)

    def encode_pil_images(self, images: list[Image.Image]) -> torch.Tensor:
        return self._forward_features(images)


def create_model(model_id: str, *, projection_dim: int = 256) -> BaseRetrievalModel:
    spec = get_experiment_model_spec(model_id)
    if spec.family == "clip":
        return ClipImageEncoder(spec)
    if model_id == "dinov2_base_pretrained":
        return DinoRetrievalModel(spec, projection_dim=None, train_backbone=False, unfreeze_last_blocks=0)
    if model_id == "dinov2_base_transfer":
        return DinoRetrievalModel(spec, projection_dim=projection_dim, train_backbone=False, unfreeze_last_blocks=0)
    if model_id == "dinov2_base_finetuned":
        return DinoRetrievalModel(spec, projection_dim=projection_dim, train_backbone=True, unfreeze_last_blocks=2)
    raise ValueError(f"unsupported model id: {model_id}")


def load_checkpoint(model: BaseRetrievalModel, checkpoint_path: Path) -> dict[str, object]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(checkpoint["model_state_dict"])
    return checkpoint
