from base64 import b64encode
from io import BytesIO
from math import sqrt

from PIL import Image, ImageOps

from .embedder import get_embedder


def generate_gradcam_overlay(image_bytes: bytes) -> dict:
    embedder = get_embedder()
    embedder._load()

    torch = embedder._torch
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
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
    colored = ImageOps.colorize(gray, black="#0f172a", white="#f97316").convert("RGBA")
    colored.putalpha(gray.point(lambda value: int(value * 0.55)))

    overlay = Image.alpha_composite(image.convert("RGBA"), colored)
    buffer = BytesIO()
    overlay.save(buffer, format="PNG")
    return {"overlay_b64": b64encode(buffer.getvalue()).decode("utf-8"), "width": image.width, "height": image.height}
