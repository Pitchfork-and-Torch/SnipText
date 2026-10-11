"""Start with Windows / login-item helpers."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Optional

APP_RUN_NAME = "SnipText"


def launch_command() -> str:
    """Command that starts SnipText (exe when frozen, otherwise python -m)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Prefer py -3 -m on Windows if available
    root = Path(__file__).resolve().parents[2]
    py = sys.executable
    return f'"{py}" -m sniptext'


def is_start_with_windows_enabled() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, APP_RUN_NAME)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception:
        return False


def set_start_with_windows(enabled: bool) -> tuple[bool, str]:
    """
    Enable/disable HKCU Run entry. Returns (ok, message).
    Non-Windows: no-op success with explanation.
    """
    if platform.system() != "Windows":
        return True, "Start with login is only configured automatically on Windows."

    try:
        import winreg

        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            path,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_READ,
        ) as key:
            if enabled:
                cmd = launch_command()
                # When running from source, set PYTHONPATH via a small wrapper is hard
                # in Run keys. Prefer frozen exe; for source use -m with working dir.
                if not getattr(sys, "frozen", False):
                    root = Path(__file__).resolve().parents[2]
                    cmd = (
                        f'"{sys.executable}" -c '
                        f'"import os,sys; os.chdir(r\'{root}\'); '
                        f'sys.path.insert(0, r\'{root}\'); '
                        f'from sniptext.app import main; main()"'
                    )
                winreg.SetValueEx(key, APP_RUN_NAME, 0, winreg.REG_SZ, cmd)
                return True, "SnipText will start when you sign in to Windows."
            try:
                winreg.DeleteValue(key, APP_RUN_NAME)
            except FileNotFoundError:
                pass
            return True, "Start with Windows disabled."
    except Exception as exc:
        return False, f"Could not update startup setting: {exc}"
