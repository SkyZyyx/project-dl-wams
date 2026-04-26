from base64 import b64encode
from io import BytesIO
from math import sqrt

from PIL import Image, ImageOps

from .embedder import get_embedder
from .model_registry import get_model_spec


def generate_gradcam_overlay(image_bytes: bytes, model_id: str | None = None) -> dict:
    spec = get_model_spec(model_id)
    if not spec.gradcam_supported:
        raise ValueError(f"gradcam is not supported for model '{spec.model_id}'")

    embedder = get_embedder(spec.model_id)
    embedder._load()

    torch = embedder._torch
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    if getattr(embedder.model, "processor", None) is not None:
        inputs = embedder.processor(images=image, return_tensors="pt")
        inputs = {key: value.to(embedder.device) for key, value in inputs.items()}

        embedder.model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            outputs = embedder.model(**inputs)
            tokens = outputs.last_hidden_state
            tokens.retain_grad()
            score = tokens[:, 0, :].pow(2).sum(dim=1).mean()
            score.backward()

        patch_tokens = tokens[:, 1:, :]
        gradients = tokens.grad[:, 1:, :]
    elif hasattr(embedder.model, "backbone") and hasattr(embedder.model, "_transform"):
        pixel_values = embedder.model._transform(image).unsqueeze(0).to(embedder.device)
        embedder.model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            tokens = embedder.model.backbone.forward_features(pixel_values)
            if not hasattr(tokens, "ndim") or tokens.ndim != 3:
                raise ValueError("gradcam tokens unavailable for this backbone")
            tokens.retain_grad()
            cls_embedding = tokens[:, 0, :]
            projected = embedder.model.projection(cls_embedding)
            score = projected.pow(2).sum(dim=1).mean()
            score.backward()

        patch_tokens = tokens[:, 1:, :]
        gradients = tokens.grad[:, 1:, :]
    else:
        raise ValueError(f"gradcam is not supported for model '{spec.model_id}'")
    cam = torch.relu((patch_tokens * gradients).sum(dim=-1))[0]
    cam = cam - cam.min()
    if cam.max().item() > 0:
        cam = cam / cam.max()

    patch_count = cam.shape[0]
    grid = int(sqrt(patch_count))
    if grid * grid != patch_count:
        raise ValueError("gradcam patch grid is not square")

    heatmap = cam.reshape(grid, grid).unsqueeze(0).unsqueeze(0)
    heatmap = torch.nn.functional.interpolate(
        heatmap,
        size=(image.height, image.width),
        mode="bilinear",
        align_corners=False,
    )[0, 0].clamp(0, 1)

    gray = Image.fromarray((heatmap.mul(255).cpu().byte().numpy()), mode="L")
    # Use a highly visible colormap (dark blue to bright red/yellow)
    # We can fake a jet-like colormap by colorizing to red, or simply use a strong red/orange
    colored = ImageOps.colorize(gray, black="#000000", white="#ff0000").convert("RGBA")
    # Increase the alpha scaling so the heatmap is significantly more visible (e.g. 0.85 instead of 0.55)
    colored.putalpha(gray.point(lambda value: int(value * 0.85)))

    overlay = Image.alpha_composite(image.convert("RGBA"), colored)
    buffer = BytesIO()
    overlay.save(buffer, format="PNG")
    return {"overlay_b64": b64encode(buffer.getvalue()).decode("utf-8"), "width": image.width, "height": image.height}
