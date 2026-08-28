"""Headless smoke test (no tray / overlay). Run: py -3 scripts/smoke_test.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw

from sniptext.capture.grabber import capture_region
from sniptext.capture.monitors import list_monitors
from sniptext.services.config import DEFAULT_CONFIG
from sniptext.services.hotkey import hotkey_to_pynput, normalize_hotkey
from sniptext.transcribe.router import EngineRouter


def main() -> int:
    assert normalize_hotkey("Ctrl+Shift+T") == "ctrl+shift+t"
    assert "ctrl" in hotkey_to_pynput("ctrl+shift+t")

    mons = list_monitors()
    assert mons, "No monitors from mss"
    m = mons[0]
    img = capture_region((m.left + 5, m.top + 5, 80, 40))
    assert img.size[0] == 80

    sample = Image.new("RGB", (480, 100), "white")
    d = ImageDraw.Draw(sample)
    d.text((20, 35), "SnipText smoke 42", fill="black")

    router = EngineRouter(DEFAULT_CONFIG)
    avail = router.list_available()
    print("engines:", avail)
    if not avail["local"] and not avail["vision"]:
        print("WARN: no engines available (install requirements-local.txt or add API key)")
        return 0

    result = router.transcribe(sample)
    print("result engine=", result.engine, "text=", repr(result.text), "err=", result.error)
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
