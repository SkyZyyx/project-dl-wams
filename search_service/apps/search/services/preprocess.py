from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageChops
from django.conf import settings

try:
    from rembg import remove as rembg_remove
except Exception:  # optional dependency
    rembg_remove = None


def preprocess_image_bytes(image_bytes: bytes) -> bytes:
    if not settings.SEARCH_PREPROCESS_ENABLED:
        return image_bytes

    if settings.SEARCH_PREPROCESS_USE_REMBG and rembg_remove is not None:
        cropped = _crop_with_rembg(image_bytes)
        if cropped is not None:
            return cropped

    cropped = _crop_foreground(image_bytes)
    return cropped if cropped is not None else image_bytes


def _crop_with_rembg(image_bytes: bytes) -> bytes | None:
    try:
        removed = rembg_remove(image_bytes)
    except Exception:
        return None

    try:
        image = Image.open(BytesIO(removed)).convert("RGBA")
    except Exception:
        return None

    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 0 else 0).getbbox()
    return _crop_and_serialize(image, bbox)


def _crop_foreground(image_bytes: bytes) -> bytes | None:
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None

    bbox = _detect_foreground_bbox(image)
    return _crop_and_serialize(image, bbox)


def _detect_foreground_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    width, height = image.size
    if width == 0 or height == 0:
        return None

    background_color = _estimate_background_color(image)
    background = Image.new("RGB", image.size, background_color)
    diff = ImageChops.difference(image, background).convert("L")
    mask = diff.point(lambda value: 255 if value > settings.SEARCH_PREPROCESS_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None or bbox == (0, 0, width, height):
        return None

    left, top, right, bottom = bbox
    area_ratio = ((right - left) * (bottom - top)) / float(width * height)
    if area_ratio < settings.SEARCH_PREPROCESS_MIN_AREA_RATIO:
        return None
    return bbox


def _estimate_background_color(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    sample_points = [
        (0, 0),
        (max(width - 1, 0), 0),
        (0, max(height - 1, 0)),
        (max(width - 1, 0), max(height - 1, 0)),
    ]
    samples = [image.getpixel(point) for point in sample_points]
    return tuple(sum(pixel[index] for pixel in samples) // len(samples) for index in range(3))


def _crop_and_serialize(image: Image.Image, bbox: tuple[int, int, int, int] | None) -> bytes | None:
    if bbox is None:
        return None

    width, height = image.size
    left, top, right, bottom = bbox
    pad = settings.SEARCH_PREPROCESS_PAD
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(width, right + pad)
    bottom = min(height, bottom + pad)

    if left == 0 and top == 0 and right == width and bottom == height:
        return None

    cropped = image.crop((left, top, right, bottom))
    buffer = BytesIO()
    cropped.save(buffer, format="PNG")
    return buffer.getvalue()
