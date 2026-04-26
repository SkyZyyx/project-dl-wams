from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


def _optional_path_setting(name: str) -> str | None:
    value = getattr(settings, name, "")
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    label: str
    family: str
    source: str
    checkpoint_path: str | None
    vector_size: int
    collection_name: str
    gradcam_supported: bool


def _build_registry() -> dict[str, ModelSpec]:
    dinov2_pretrained_source = getattr(
        settings,
        "DINOV2_PRETRAINED_SOURCE",
        getattr(settings, "DINOv2_PRETRAINED_SOURCE", "facebook/dinov2-base"),
    )
    return {
        "clip_vit_b32_pretrained": ModelSpec(
            model_id="clip_vit_b32_pretrained",
            label="CLIP ViT-B/32 (pretrained, no fine-tune)",
            family="clip",
            source=getattr(settings, "CLIP_VIT_B32_SOURCE", "openai/clip-vit-base-patch32"),
            checkpoint_path=_optional_path_setting("CLIP_VIT_B32_CHECKPOINT_PATH"),
            vector_size=512,
            collection_name="product_images_clip_vit_b32_pretrained",
            gradcam_supported=False,
        ),
        "dinov2_base_pretrained": ModelSpec(
            model_id="dinov2_base_pretrained",
            label="DINOv2-base (pretrained, no fine-tune)",
            family="dinov2",
            source=dinov2_pretrained_source,
            checkpoint_path=None,
            vector_size=768,
            collection_name="product_images_dinov2_base_pretrained",
            gradcam_supported=True,
        ),
        "dinov2_base_transfer": ModelSpec(
            model_id="dinov2_base_transfer",
            label="DINOv2-base + transfer learning",
            family="dinov2",
            source=getattr(settings, "DINOV2_TRANSFER_SOURCE", getattr(settings, "DINOv2_TRANSFER_SOURCE", dinov2_pretrained_source)),
            checkpoint_path=_optional_path_setting("DINOV2_TRANSFER_CHECKPOINT_PATH")
            or _optional_path_setting("DINOv2_TRANSFER_CHECKPOINT_PATH"),
            vector_size=768,
            collection_name="product_images_dinov2_base_transfer",
            gradcam_supported=True,
        ),
        "dinov2_base_finetuned": ModelSpec(
            model_id="dinov2_base_finetuned",
            label="DINOv2-base fine-tuned",
            family="dinov2",
            source=getattr(settings, "DINOV2_FINETUNED_SOURCE", getattr(settings, "DINOv2_FINETUNED_SOURCE", dinov2_pretrained_source)),
            checkpoint_path=_optional_path_setting("DINOV2_FINETUNED_CHECKPOINT_PATH")
            or _optional_path_setting("DINOv2_FINETUNED_CHECKPOINT_PATH"),
            vector_size=768,
            collection_name="product_images_dinov2_base_finetuned",
            gradcam_supported=True,
        ),
        "dinov2_base_triplet_finetuned": ModelSpec(
            model_id="dinov2_base_triplet_finetuned",
            label="DINOv2-base triplet fine-tuned",
            family="dinov2",
            source=getattr(
                settings,
                "DINOV2_TRIPLET_FINETUNED_SOURCE",
                getattr(settings, "DINOv2_TRIPLET_FINETUNED_SOURCE", "vit_base_patch14_dinov2.lvd142m"),
            ),
            checkpoint_path=_optional_path_setting("DINOV2_TRIPLET_FINETUNED_CHECKPOINT_PATH")
            or _optional_path_setting("DINOv2_TRIPLET_FINETUNED_CHECKPOINT_PATH"),
            vector_size=max(
                1,
                int(getattr(settings, "DINOV2_TRIPLET_FINETUNED_VECTOR_SIZE", getattr(settings, "DINOv2_TRIPLET_FINETUNED_VECTOR_SIZE", 512))),
            ),
            collection_name="product_images_dinov2_base_triplet_finetuned",
            gradcam_supported=True,
        ),
    }


def get_default_model_id() -> str:
    return getattr(settings, "DEFAULT_SEARCH_MODEL", "dinov2_base_pretrained")


def get_model_registry() -> dict[str, ModelSpec]:
    return _build_registry().copy()


def get_model_spec(model_id: str | None = None) -> ModelSpec:
    resolved_model_id = model_id or get_default_model_id()
    registry = _build_registry()
    try:
        return registry[resolved_model_id]
    except KeyError as exc:
        raise ValueError(f"unknown model id: {resolved_model_id}") from exc
