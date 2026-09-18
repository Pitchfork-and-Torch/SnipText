"""API key storage: OS keyring preferred, file fallback with warning."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from sniptext.services.config import APP_ID, config_dir

SERVICE = APP_ID
KEY_NAMES = (
    "xai_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "google_api_key",
)

_FILE_WARNING_SHOWN = False


def secrets_file() -> Path:
    return config_dir() / "secrets.json"


def _keyring_get(name: str) -> Optional[str]:
    try:
        import keyring

        val = keyring.get_password(SERVICE, name)
        return val if val else None
    except Exception:
        return None


def _keyring_set(name: str, value: str) -> bool:
    try:
        import keyring

        if value:
            keyring.set_password(SERVICE, name, value)
        else:
            try:
                keyring.delete_password(SERVICE, name)
            except Exception:
                pass
        return True
    except Exception:
        return False


def _file_load() -> dict[str, str]:
    path = secrets_file()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: str(v) for k, v in data.items() if v} if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _file_save(data: dict[str, str]) -> None:
    global _FILE_WARNING_SHOWN
    path = secrets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    if not _FILE_WARNING_SHOWN:
        print(
            f"[SnipText] WARNING: API keys stored in {path} "
            "(keyring unavailable). Prefer OS credential store.",
            file=sys.stderr,
        )
        _FILE_WARNING_SHOWN = True


_ENV_MAP = {
    "xai_api_key": ("XAI_API_KEY", "GROK_API_KEY"),
    "openai_api_key": ("OPENAI_API_KEY",),
    "anthropic_api_key": ("ANTHROPIC_API_KEY",),
    "google_api_key": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


def get_secret(name: str) -> Optional[str]:
    val = _keyring_get(name)
    if val:
        return val
    file_val = _file_load().get(name)
    if file_val:
        return file_val
    import os

    for env_name in _ENV_MAP.get(name, ()):
        env_val = os.environ.get(env_name)
        if env_val and env_val.strip():
            return env_val.strip()
    return None


def set_secret(name: str, value: str) -> None:
    value = (value or "").strip()
    if _keyring_set(name, value):
        # keep file in sync cleaned if it existed
        data = _file_load()
        if name in data:
            if value:
                data[name] = value
            else:
                data.pop(name, None)
            if data:
                _file_save(data)
            elif secrets_file().is_file():
                try:
                    secrets_file().unlink()
                except OSError:
                    pass
        return
    data = _file_load()
    if value:
        data[name] = value
    else:
        data.pop(name, None)
    if data:
        _file_save(data)
    elif secrets_file().is_file():
        try:
            secrets_file().unlink()
        except OSError:
            pass


def get_all_keys() -> dict[str, Optional[str]]:
    return {name: get_secret(name) for name in KEY_NAMES}


def has_any_vision_key() -> bool:
    return any(get_secret(n) for n in KEY_NAMES)
