"""First-run OS permission guidance (strings only)."""

from __future__ import annotations

import platform


def permission_checklist() -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return [
            "System Settings -> Privacy & Security -> Screen Recording: enable SnipText (or Terminal/Python while developing).",
            "System Settings -> Privacy & Security -> Accessibility: enable SnipText for global hotkeys.",
            "After changing permissions, quit and relaunch SnipText.",
        ]
    if system == "Linux":
        return [
            "X11: capture and hotkeys usually work without extra setup.",
            "Wayland: global hotkeys and full-screen capture may be limited; prefer an X11 session if possible.",
            "Install xclip or wl-copy for clipboard support if text does not copy.",
        ]
    # Windows
    return [
        "No special Screen Recording permission is required on Windows.",
        "If the hotkey does not fire over elevated apps, run SnipText elevated or use the tray menu New snip.",
        "Some secure desktops (UAC, login) cannot be captured - that is an OS limit.",
    ]


def first_run_message() -> str:
    lines = [
        "Welcome to SnipText",
        "",
        "Hotkey (default): Ctrl+Shift+T (Cmd+Shift+T on macOS)",
        "1. Press the hotkey",
        "2. Drag a rectangle over on-screen text",
        "3. Release - text is transcribed and copied to the clipboard",
        "",
        "For maximum accuracy, add an xAI API key in Settings (uses Grok vision).",
        "Without a key, SnipText uses local OCR on your machine only.",
        "",
        "Permissions:",
    ]
    lines.extend(f"  - {item}" for item in permission_checklist())
    return "\n".join(lines)
