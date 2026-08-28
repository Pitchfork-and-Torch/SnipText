"""First-run onboarding with inline AI key connect."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from typing import Callable, Optional

from sniptext.services import secrets
from sniptext.services.config import save_config
from sniptext.services.permissions import permission_checklist
from sniptext.services.providers import (
    PROVIDERS,
    provider_status_line,
    test_provider_connection,
)
from sniptext.services.readiness import readiness_summary

BG = "#0f172a"
CARD = "#1e293b"
FG = "#e2e8f0"
MUTED = "#94a3b8"
ACCENT = "#5BDBFF"
BTN = "#0ea5e9"
BTN_FG = "#0f172a"
OK = "#22c55e"
DANGER = "#f87171"


def show_onboarding(
    parent: tk.Misc,
    config: Optional[dict] = None,
    on_done: Optional[Callable[[dict], None]] = None,
    on_open_settings: Optional[Callable[[], None]] = None,
) -> None:
    cfg = dict(config or {})
    win = tk.Toplevel(parent)
    win.title("Welcome to SnipText")
    try:
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    win.configure(bg=BG)
    win.geometry("540x560+120+80")
    win.minsize(480, 480)

    tk.Label(
        win,
        text="Welcome to SnipText",
        fg=ACCENT,
        bg=BG,
        font=("Segoe UI", 18, "bold"),
    ).pack(anchor="w", padx=18, pady=(16, 2))
    tk.Label(
        win,
        text="Snip. Read. Clipboard.  -  Press Ctrl+Shift+T, drag, release.",
        fg=MUTED,
        bg=BG,
        font=("Segoe UI", 10),
    ).pack(anchor="w", padx=18)

    # Steps
    body = tk.Frame(win, bg=BG)
    body.pack(fill="both", expand=True, padx=18, pady=12)

    tk.Label(
        body,
        text="1. Connect AI for maximum accuracy (optional but recommended)",
        fg=FG,
        bg=BG,
        font=("Segoe UI", 10, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(0, 6))

    provider = PROVIDERS[0]  # xAI recommended
    tk.Label(
        body,
        text=provider.help_blurb,
        fg=MUTED,
        bg=BG,
        font=("Segoe UI", 9),
        wraplength=480,
        justify="left",
        anchor="w",
    ).pack(fill="x")

    link_row = tk.Frame(body, bg=BG)
    link_row.pack(fill="x", pady=(8, 4))
    tk.Button(
        link_row,
        text="Get free xAI API key",
        command=lambda: webbrowser.open(provider.get_key_url),
        bg=CARD,
        fg=FG,
        relief="flat",
        padx=10,
        pady=5,
        font=("Segoe UI", 9),
        cursor="hand2",
    ).pack(side="left")
    tk.Label(
        link_row,
        text="Opens console.x.ai in your browser",
        fg=MUTED,
        bg=BG,
        font=("Segoe UI", 8),
    ).pack(side="left", padx=10)

    tk.Label(body, text="Paste API key", fg=MUTED, bg=BG, font=("Segoe UI", 9)).pack(
        anchor="w", pady=(8, 2)
    )
    key_var = tk.StringVar()
    key_entry = tk.Entry(
        body,
        textvariable=key_var,
        show="*",
        bg=CARD,
        fg="#f8fafc",
        insertbackground="#f8fafc",
        relief="flat",
        font=("Consolas", 10),
    )
    key_entry.pack(fill="x", ipady=7)

    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(
        body,
        textvariable=status_var,
        fg=MUTED,
        bg=BG,
        font=("Segoe UI", 9),
        wraplength=480,
        justify="left",
        anchor="w",
    )
    status_lbl.pack(fill="x", pady=(6, 0))

    testing = {"v": False}

    def set_status(msg: str, ok: Optional[bool] = None) -> None:
        status_var.set(msg)
        if ok is True:
            status_lbl.configure(fg=OK)
        elif ok is False:
            status_lbl.configure(fg=DANGER)
        else:
            status_lbl.configure(fg=MUTED)

    def test_and_save() -> None:
        if testing["v"]:
            return
        key = key_var.get().strip()
        if not key:
            set_status("Paste your key first, or continue with local OCR.", False)
            return
        testing["v"] = True
        test_btn.configure(state="disabled", text="Testing...")
        set_status("Testing xAI vision connection...")

        def worker() -> None:
            ok, msg = test_provider_connection("xai", key, model="grok-4.5")

            def done() -> None:
                testing["v"] = False
                test_btn.configure(state="normal", text="Test & save key")
                set_status(msg, ok)
                if ok:
                    secrets.set_secret("xai_api_key", key)
                    key_var.set("")
                    cfg["engine_mode"] = "ai_first"
                    cfg["vision_model"] = "grok-4.5"
                    cfg["first_run_complete"] = True
                    save_config(cfg)
                    if on_done:
                        on_done(cfg)

            try:
                win.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    btn_row = tk.Frame(body, bg=BG)
    btn_row.pack(fill="x", pady=(10, 12))
    test_btn = tk.Button(
        btn_row,
        text="Test & save key",
        command=test_and_save,
        bg=BTN,
        fg=BTN_FG,
        relief="flat",
        padx=12,
        pady=6,
        font=("Segoe UI", 10, "bold"),
        cursor="hand2",
    )
    test_btn.pack(side="left")
    tk.Button(
        btn_row,
        text="Other providers...",
        command=lambda: (close(), on_open_settings() if on_open_settings else None),
        bg=CARD,
        fg=FG,
        relief="flat",
        padx=10,
        pady=6,
        font=("Segoe UI", 9),
        cursor="hand2",
    ).pack(side="left", padx=8)

    # Local OCR status
    tk.Label(
        body,
        text="2. Local OCR (offline backup)",
        fg=FG,
        bg=BG,
        font=("Segoe UI", 10, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(10, 4))
    tk.Label(
        body,
        text=readiness_summary(),
        fg=MUTED,
        bg=BG,
        font=("Segoe UI", 8),
        wraplength=480,
        justify="left",
        anchor="w",
    ).pack(fill="x")

    # Permissions
    tk.Label(
        body,
        text="3. Permissions on this PC",
        fg=FG,
        bg=BG,
        font=("Segoe UI", 10, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(8, 4))
    for item in permission_checklist():
        tk.Label(
            body,
            text=f"  - {item}",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 8),
            wraplength=480,
            justify="left",
            anchor="w",
        ).pack(fill="x")

    def close() -> None:
        cfg["first_run_complete"] = True
        save_config(cfg)
        if on_done:
            on_done(cfg)
        try:
            win.destroy()
        except tk.TclError:
            pass

    foot = tk.Frame(win, bg=BG)
    foot.pack(fill="x", padx=18, pady=(0, 16))
    tk.Button(
        foot,
        text="Continue with local OCR",
        command=close,
        bg=CARD,
        fg=FG,
        relief="flat",
        padx=12,
        pady=6,
        font=("Segoe UI", 9),
        cursor="hand2",
    ).pack(side="right")
    tk.Label(
        foot,
        text=provider_status_line(),
        fg=MUTED,
        bg=BG,
        font=("Segoe UI", 8),
    ).pack(side="left")

    win.protocol("WM_DELETE_WINDOW", close)
    try:
        key_entry.focus_set()
    except tk.TclError:
        pass
