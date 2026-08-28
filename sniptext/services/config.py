"""Config load/save in standard user locations."""

from __future__ import annotations

import json
import os
import platform
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "SnipText"
APP_ID = "sniptext"

DEFAULT_CONFIG: dict[str, Any] = {
    "hotkey": "ctrl+shift+t" if platform.system() != "Darwin" else "cmd+shift+t",
    "engine_mode": "ai_first",  # ai_first | local_only | ai_only
    "vision_model": "grok-4.5",
    "vision_detail": "high",
    "output_format": "markdown",  # markdown | plain
    "languages": ["en"],
    "theme": "system",  # system | dark | light
    "show_preview": True,
    "notifications": True,
    "shutter_sound": True,
    "history_limit": 50,
    "local_engine_order": ["paddle", "rapid", "easyocr", "tesseract"],
    "first_run_complete": False,
    "copy_image_too": False,
    "preview_auto_dismiss_sec": 8,
    # Delay (seconds) before selection overlay - lets menus stay open
    "snip_delay_sec": 0,
    # Windows login start (mirrored to registry on save)
    "start_with_windows": False,
    "dismissed_ai_nudge": False,
    "dismissed_ocr_nudge": False,
}


def config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / APP_NAME
    elif system == "Darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        path = Path(xdg) / APP_ID if xdg else Path.home() / ".config" / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def history_path() -> Path:
    return config_dir() / "history.json"


def log_path() -> Path:
    return config_dir() / "sniptext.log"


def load_config() -> dict[str, Any]:
    path = config_path()
    cfg = deepcopy(DEFAULT_CONFIG)
    if path.is_file():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[SnipText] config load failed: {exc}", file=sys.stderr)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never write secrets into config
    safe = {k: v for k, v in cfg.items() if not str(k).endswith("_api_key")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2, ensure_ascii=False)
        f.write("\n")
