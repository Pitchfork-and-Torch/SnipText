"""Image pre-processing for OCR accuracy."""

from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def prepare_for_ocr(image: Image.Image, *, for_vision: bool = False) -> Image.Image:
    """Return a processed RGB image. Vision path keeps high res with light contrast only."""
    img = image.convert("RGB")
    if for_vision:
        # Keep native resolution; mild contrast only
        img = ImageOps.autocontrast(img, cutoff=0.5)
        return img

    w, h = img.size
    min_side = min(w, h)
    # Upscale small UI text regions (LANCZOS keeps edges sharper than bicubic)
    if min_side < 500:
        scale = min(3.0, 700 / max(min_side, 1))
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    elif min_side < 900:
        img = img.resize((int(w * 1.5), int(h * 1.5)), Image.Resampling.LANCZOS)

    img = ImageOps.autocontrast(img, cutoff=0.5)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)
    # Sharpen slightly for UI screenshots - skip median denoise (kills thin fonts)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def to_png_bytes(image: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
