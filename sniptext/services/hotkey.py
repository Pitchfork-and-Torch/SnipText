"""Global hotkey listener via pynput."""

from __future__ import annotations

import platform
import re
import sys
import threading
from typing import Callable, Optional

# Map friendly names to pynput Key / char tokens
_MOD_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "cmd": "cmd",
    "command": "cmd",
    "super": "cmd",
    "win": "cmd",
    "alt": "alt",
    "option": "alt",
    "shift": "shift",
}


def normalize_hotkey(spec: str) -> str:
    parts = [p.strip().lower() for p in re.split(r"[+\-]", spec or "") if p.strip()]
    mods: list[str] = []
    key = ""
    for p in parts:
        if p in _MOD_ALIASES:
            m = _MOD_ALIASES[p]
            if m not in mods:
                mods.append(m)
        else:
            key = p
    if platform.system() == "Darwin":
        mods = ["cmd" if m == "ctrl" and "cmd" not in mods else m for m in mods]
    order = ["ctrl", "cmd", "alt", "shift"]
    mods_sorted = [m for m in order if m in mods]
    return "+".join(mods_sorted + ([key] if key else []))


def hotkey_to_pynput(spec: str) -> str:
    """Convert 'ctrl+shift+t' to pynput GlobalHotKeys format '<ctrl>+<shift>+t'."""
    norm = normalize_hotkey(spec)
    parts = norm.split("+")
    out: list[str] = []
    for p in parts:
        if p in ("ctrl", "alt", "shift", "cmd"):
            out.append(f"<{p}>")
        elif len(p) == 1:
            out.append(p)
        else:
            # f-keys etc
            out.append(f"<{p}>")
    return "+".join(out)


class HotkeyService:
    def __init__(self) -> None:
        self._listener = None
        self._lock = threading.Lock()
        self._callback: Optional[Callable[[], None]] = None
        self._spec: str = ""

    def start(self, spec: str, callback: Callable[[], None]) -> bool:
        self.stop()
        self._callback = callback
        self._spec = normalize_hotkey(spec)
        combo = hotkey_to_pynput(self._spec)

        def _on_activate() -> None:
            if self._callback:
                try:
                    self._callback()
                except Exception as exc:
                    print(f"[SnipText] hotkey callback error: {exc}", file=sys.stderr)

        try:
            from pynput import keyboard

            mapping = {combo: _on_activate}
            listener = keyboard.GlobalHotKeys(mapping)
            listener.daemon = True
            listener.start()
            self._listener = listener
            return True
        except Exception as exc:
            print(f"[SnipText] hotkey start failed ({combo}): {exc}", file=sys.stderr)
            self._listener = None
            return False

    def stop(self) -> None:
        with self._lock:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None

    def restart(self, spec: str, callback: Callable[[], None]) -> bool:
        return self.start(spec, callback)

    @property
    def current(self) -> str:
        return self._spec
