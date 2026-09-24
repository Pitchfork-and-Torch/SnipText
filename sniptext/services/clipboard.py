"""Cross-platform clipboard helpers."""

from __future__ import annotations

import ctypes
import io
import platform
import subprocess
import sys
from ctypes import wintypes
from typing import Optional

from PIL import Image

from sniptext.services.image_in import dib_from_image, image_from_clipboard_payloads

CF_DIB = 8
CF_UNICODETEXT = 13
CF_DIBV5 = 17
_GMEM_MOVEABLE = 0x0002


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


def get_image() -> Optional[Image.Image]:
    """Read an image already on the clipboard. Does not clear it. Does not write a file."""
    if platform.system() != "Windows":
        return None
    try:
        png, dib = _read_windows_image_payloads()
    except Exception as exc:
        print(f"[SnipText] clipboard image read failed: {exc}", file=sys.stderr)
        return None
    return image_from_clipboard_payloads(png, dib)


def deliver(text: str, image: Optional[Image.Image] = None) -> bool:
    """Put text on the clipboard. On Windows, also keep the image when asked.

    A second clipboard write that empties the board would drop the text.
    """
    if image is not None and platform.system() == "Windows":
        try:
            if _set_windows_text_and_image(text, image):
                return True
        except Exception as exc:
            print(f"[SnipText] clipboard text+image failed: {exc}", file=sys.stderr)
    return set_text(text)


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


def _clipboard_api():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    return user32, kernel32


def _read_hglobal(kernel32, handle) -> Optional[bytes]:
    if not handle:
        return None
    size = int(kernel32.GlobalSize(handle) or 0)
    if size <= 0:
        return None
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        return None
    try:
        return ctypes.string_at(ptr, size)
    finally:
        kernel32.GlobalUnlock(handle)


def _read_windows_image_payloads() -> tuple[Optional[bytes], Optional[bytes]]:
    user32, kernel32 = _clipboard_api()
    if not user32.OpenClipboard(None):
        return None, None
    try:
        png = None
        for name in ("PNG", "image/png"):
            fmt = int(user32.RegisterClipboardFormatW(name) or 0)
            if fmt and user32.IsClipboardFormatAvailable(fmt):
                png = _read_hglobal(kernel32, user32.GetClipboardData(fmt))
                if png:
                    break
        dib = None
        for fmt in (CF_DIBV5, CF_DIB):
            if user32.IsClipboardFormatAvailable(fmt):
                dib = _read_hglobal(kernel32, user32.GetClipboardData(fmt))
                if dib:
                    break
        return png, dib
    finally:
        user32.CloseClipboard()


def _global_copy(kernel32, data: bytes):
    handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
    if not handle:
        raise OSError("GlobalAlloc failed")
    ptr = kernel32.GlobalLock(handle)
    if not ptr:
        kernel32.GlobalFree(handle)
        raise OSError("GlobalLock failed")
    try:
        ctypes.memmove(ptr, data, len(data))
    finally:
        kernel32.GlobalUnlock(handle)
    return handle


def _set_windows_text_and_image(text: str, image: Image.Image) -> bool:
    user32, kernel32 = _clipboard_api()
    text_bytes = (text or "").encode("utf-16-le") + b"\x00\x00"
    dib = dib_from_image(image)
    if not user32.OpenClipboard(None):
        return False
    text_h = None
    dib_h = None
    try:
        if not user32.EmptyClipboard():
            return False
        text_h = _global_copy(kernel32, text_bytes)
        if not user32.SetClipboardData(CF_UNICODETEXT, text_h):
            return False
        text_h = None
        dib_h = _global_copy(kernel32, dib)
        if not user32.SetClipboardData(CF_DIB, dib_h):
            return True
        dib_h = None
        return True
    finally:
        if text_h:
            kernel32.GlobalFree(text_h)
        if dib_h:
            kernel32.GlobalFree(dib_h)
        user32.CloseClipboard()
