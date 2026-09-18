"""Play the bundled camera shutter click after a successful snip."""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

log = logging.getLogger("sniptext.shutter")


def assets_dir() -> Path:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "assets")
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
        candidates.append(root / "assets")
        candidates.append(root / "_internal" / "assets")
    candidates.append(Path(__file__).resolve().parents[2] / "assets")
    for folder in candidates:
        if (folder / "shutter.wav").is_file():
            return folder
    return candidates[0]


def shutter_path() -> Path:
    return assets_dir() / "shutter.wav"


def play_shutter(enabled: bool = True) -> None:
    """Fire-and-forget. Never raise into the snip pipeline."""
    if not enabled:
        return
    path = shutter_path()
    if not path.is_file():
        log.debug("No shutter wav at %s", path)
        return
    try:
        if platform.system() == "Windows":
            import winsound

            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
            return
        # Best-effort on other OS; Windows EXE is the product path.
        import subprocess

        if platform.system() == "Darwin":
            subprocess.Popen(
                ["afplay", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["aplay", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as exc:
        log.debug("Shutter play skipped: %s", exc)
