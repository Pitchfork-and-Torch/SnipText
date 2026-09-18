"""Generate an original camera-shutter WAV (no third-party samples)."""

from __future__ import annotations

import math
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "shutter.wav"
RATE = 44100
AMP = 22000


def _env(i: int, n: int, attack: int = 12) -> float:
    if n <= 0:
        return 0.0
    if i < attack:
        return i / attack
    t = (i - attack) / max(1, n - attack)
    return math.exp(-6.5 * t)


def click(samples: list[int], start: int, n: int, gain: float, f_hi: float, f_lo: float) -> None:
    for i in range(n):
        e = _env(i, n) * gain
        t = i / RATE
        hi = math.sin(2 * math.pi * f_hi * t)
        lo = math.sin(2 * math.pi * f_lo * t)
        noise = ((i * 1103515245 + 12345) % 32768) / 32768.0 - 0.5
        val = e * (0.55 * hi + 0.28 * lo + 0.17 * noise)
        idx = start + i
        if 0 <= idx < len(samples):
            samples[idx] += int(AMP * val)


def main() -> None:
    total = int(RATE * 0.22)
    samples = [0] * total
    click(samples, 0, int(RATE * 0.055), 1.0, 2850.0, 95.0)
    click(samples, int(RATE * 0.085), int(RATE * 0.07), 0.72, 2400.0, 80.0)
    peak = max(1, max(abs(s) for s in samples))
    scale = AMP / peak
    pcm = [max(-32767, min(32767, int(s * scale))) for s in samples]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(int(s).to_bytes(2, "little", signed=True) for s in pcm))
    print("wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
