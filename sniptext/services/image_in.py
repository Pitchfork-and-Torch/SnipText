"""In-memory image decode for clipboard and file intake.

Snip pictures are not written to disk here. History stores text only.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

_BI_BITFIELDS = 3


def flatten_rgb(image: Image.Image) -> Image.Image:
    """RGB on white so transparent pixels do not become black before OCR."""
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return image.convert("RGB")


def bmp_file_from_dib(dib: bytes) -> bytes:
    """Wrap a clipboard CF_DIB / CF_DIBV5 blob in a BMP file header."""
    if len(dib) < 16:
        raise ValueError("DIB is too short")
    header_size = struct.unpack_from("<I", dib, 0)[0]
    if header_size < 40 or header_size > len(dib):
        raise ValueError("DIB header size is not usable")
    bitcount = struct.unpack_from("<H", dib, 14)[0]
    compression = struct.unpack_from("<I", dib, 16)[0]
    clr_used = struct.unpack_from("<I", dib, 32)[0] if header_size >= 36 else 0
    if bitcount <= 8:
        colors = clr_used or (1 << bitcount)
        palette = colors * 4
    else:
        palette = clr_used * 4
    masks = 12 if compression == _BI_BITFIELDS and header_size == 40 else 0
    off = 14 + header_size + palette + masks
    blob = struct.pack("<2sIHHI", b"BM", 14 + len(dib), 0, 0, off) + dib
    return blob


def image_from_dib(dib: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(bmp_file_from_dib(dib)))
    img.load()
    return flatten_rgb(img)


def image_from_png_bytes(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return flatten_rgb(img)


def image_from_clipboard_payloads(
    png: bytes | None = None,
    dib: bytes | None = None,
) -> Image.Image | None:
    """Prefer PNG bytes, then a DIB. Never touches the OS clipboard."""
    if png:
        try:
            return image_from_png_bytes(png)
        except Exception:
            pass
    if dib:
        try:
            return image_from_dib(dib)
        except Exception:
            return None
    return None


def dib_from_image(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    flatten_rgb(image).save(buf, format="BMP")
    data = buf.getvalue()
    if len(data) <= 14 or data[:2] != b"BM":
        raise ValueError("BMP encode failed")
    return data[14:]


def load_image_file(path: Path) -> Image.Image:
    """Open a local image. Errors name the file, not a full path."""
    src = Path(path)
    if not src.is_file():
        raise ValueError(f"Could not read {src.name}")
    try:
        img = Image.open(src)
        img.load()
        if getattr(img, "n_frames", 1) > 1:
            img.seek(0)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not read {src.name}") from exc
    return flatten_rgb(img)
