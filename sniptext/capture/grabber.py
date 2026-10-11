"""Native-resolution region capture via mss."""

from __future__ import annotations

from typing import Tuple

import mss
from PIL import Image

# Absolute screen rect: left, top, width, height in virtual desktop coords
Rect = Tuple[int, int, int, int]


def capture_region(rect: Rect) -> Image.Image:
    left, top, width, height = rect
    if width < 1 or height < 1:
        raise ValueError("Selection too small")

    region = {
        "left": int(left),
        "top": int(top),
        "width": int(width),
        "height": int(height),
    }
    with mss.mss() as sct:
        shot = sct.grab(region)
        # BGRA -> RGB
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return img


def capture_fullscreen() -> Image.Image:
    with mss.mss() as sct:
        mon = sct.monitors[0]
        shot = sct.grab(mon)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
