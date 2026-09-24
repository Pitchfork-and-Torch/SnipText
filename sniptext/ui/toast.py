"""Notifications / toast helpers."""

from __future__ import annotations

import platform
import sys
import threading
import tkinter as tk
from typing import Optional


def notify(title: str, message: str, enabled: bool = True) -> None:
    if not enabled:
        return
    # Prefer plyer
    try:
        from plyer import notification

        notification.notify(title=title, message=message, app_name="SnipText", timeout=4)
        return
    except Exception:
        pass

    # Windows toast via PowerShell (best-effort)
    if platform.system() == "Windows":
        try:
            import subprocess

            # Keep short; avoid complex escaping issues
            safe_title = title.replace("'", "")
            safe_msg = message.replace("'", "")[:180]
            ps = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                f"ContentType = WindowsRuntime] > $null; "
                f"$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                f"$text = $t.GetElementsByTagName('text'); "
                f"$text.Item(0).AppendChild($t.CreateTextNode('{safe_title}')) | Out-Null; "
                f"$text.Item(1).AppendChild($t.CreateTextNode('{safe_msg}')) | Out-Null; "
                f"$toast = [Windows.UI.Notifications.ToastNotification]::new($t); "
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SnipText').Show($toast);"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

    print(f"[SnipText] {title}: {message}", file=sys.stderr)


def show_busy_pill(parent: tk.Misc, text: str = "Transcribing...") -> tuple[tk.Toplevel, callable]:
    """Small non-blocking status pill. Returns (window, close_fn)."""
    win = tk.Toplevel(parent)
    win.overrideredirect(True)
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    win.configure(bg="#111827")
    lbl = tk.Label(
        win,
        text=text,
        fg="#E5E7EB",
        bg="#111827",
        font=("Segoe UI", 11),
        padx=16,
        pady=10,
    )
    lbl.pack()
    # bottom-right of primary-ish area
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    win.geometry(f"+{sw - w - 24}+{sh - h - 64}")

    closed = {"v": False}

    def close() -> None:
        if closed["v"]:
            return
        closed["v"] = True
        try:
            win.destroy()
        except tk.TclError:
            pass

    return win, close
