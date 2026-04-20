from io import BytesIO

from PIL import Image, ImageStat, UnidentifiedImageError


def validate_image_quality(image_bytes: bytes) -> tuple[bool, str]:
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except UnidentifiedImageError:
        return False, "invalid image"
    except Exception:
        return False, "cannot read image"

    if image.width < 64 or image.height < 64:
        return False, "image too small"

    gray = image.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = stat.mean[0]
    contrast = stat.stddev[0]

    if brightness < 15:
        return False, "image too dark"
    if brightness > 240:
        return False, "image too bright"
    if contrast < 8:
        return False, "image too blurry or flat"

    return True, "ok"
