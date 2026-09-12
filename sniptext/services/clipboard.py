"""Cross-platform clipboard helpers."""

from __future__ import annotations

import io
import platform
import subprocess
import sys
from typing import Optional

from PIL import Image


def set_text(text: str) -> bool:
    text = text if text is not None else ""
    try:
        # Prefer tkinter clipboard - reliable on Windows without extra deps
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception as exc:
        print(f"[SnipText] tk clipboard failed: {exc}", file=sys.stderr)

    system = platform.system()
    try:
        if system == "Windows":
            # clip.exe wants UTF-16LE via PowerShell is more reliable for unicode
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Set-Clipboard -Value $input",
                ],
                input=text,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=5,
            )
            return True
        if system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False, timeout=5)
            return True
        # Linux
        for cmd in (
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
            ["wl-copy"],
        ):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5)
                return True
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
    except Exception as exc:
        print(f"[SnipText] clipboard fallback failed: {exc}", file=sys.stderr)
    return False


def get_text() -> str:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            val = root.clipboard_get()
        except tk.TclError:
            val = ""
        root.destroy()
        return val or ""
    except Exception:
        return ""


def set_image(image: Image.Image) -> bool:
    """Best-effort put PNG image on clipboard (Windows-focused)."""
    try:
        system = platform.system()
        if system == "Windows":
            return _set_image_windows(image)
        # Other platforms: leave as extension point
        return False
    except Exception as exc:
        print(f"[SnipText] image clipboard failed: {exc}", file=sys.stderr)
        return False


def _set_image_windows(image: Image.Image) -> bool:
    try:
        import win32clipboard  # type: ignore
        import win32con  # type: ignore

        output = io.BytesIO()
        # CF_DIB expects BMP without file header
        bmp = image.convert("RGB")
        bmp.save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        win32clipboard.CloseClipboard()
        return True
    except ImportError:
        # Optional pywin32 - skip silently
        return False
    except Exception:
        return False
