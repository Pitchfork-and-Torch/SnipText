"""Shutter wav + play helper. Run: py -3 scripts/test_shutter.py"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sniptext.services.shutter import play_shutter, shutter_path


def main() -> int:
    path = shutter_path()
    assert path.is_file(), f"missing {path}"
    with wave.open(str(path), "r") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 44100
        n = w.getnframes()
        dur = n / 44100.0
        assert 0.12 <= dur <= 0.4, dur
    play_shutter(enabled=False)
    play_shutter(enabled=True)
    print("SHUTTER OK", path.name, f"{dur:.3f}s", path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
