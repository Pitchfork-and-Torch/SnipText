"""Settings panel - Connect AI first, then preferences."""

from __future__ import annotations

import platform
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import Callable, Optional

from sniptext.services import secrets
from sniptext.services.config import save_config
from sniptext.services.hotkey import normalize_hotkey
from sniptext.services.providers import (
    ENGINE_MODE_CHOICES,
    ENGINE_MODE_FROM_LABEL,
    ENGINE_MODE_LABELS,
    PROVIDERS,
    provider_status_line,
    test_provider_connection,
)
from sniptext.services.readiness import readiness_summary
from sniptext.services.startup import is_start_with_windows_enabled, set_start_with_windows

BG = "#0f172a"
CARD = "#1e293b"
FG = "#e2e8f0"
MUTED = "#94a3b8"
ACCENT = "#5BDBFF"
BTN = "#0ea5e9"
BTN_FG = "#0f172a"
DANGER = "#f87171"
OK = "#22c55e"


class SettingsWindow:
    def __init__(
        self,
        parent: tk.Misc,
        config: dict,
        on_save: Optional[Callable[[dict], None]] = None,
        *,
        focus_connect: bool = False,
    ) -> None:
        self.parent = parent
        self.config = dict(config)
        self.on_save = on_save
        self._testing = False
        self._recording = False
        self._record_listener = None

        self.win = tk.Toplevel(parent)
        self.win.title("SnipText Settings")
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.win.configure(bg=BG)
        self.win.geometry("560x680+100+40")
        self.win.minsize(480, 540)

        head = tk.Frame(self.win, bg=BG)
        head.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(
            head,
            text="Settings",
            fg=ACCENT,
            bg=BG,
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        self.status_var = tk.StringVar(value=provider_status_line())
        tk.Label(
            head,
            textvariable=self.status_var,
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
            wraplength=320,
            justify="right",
        ).pack(side="right")

        style = ttk.Style(self.win)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 6), font=("Segoe UI", 10))

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=12, pady=8)

        tab_ai = tk.Frame(nb, bg=BG)
        tab_prefs = tk.Frame(nb, bg=BG)
        nb.add(tab_ai, text="  Connect AI  ")
        nb.add(tab_prefs, text="  Preferences  ")
        if focus_connect:
            nb.select(0)

        self._build_connect_tab(tab_ai)
        self._build_prefs_tab(tab_prefs)

        foot = tk.Frame(self.win, bg=BG)
        foot.pack(fill="x", padx=16, pady=(4, 14))
        self._btn(foot, "Save", self._save, primary=True).pack(side="left")
        self._btn(foot, "Cancel", self._cancel).pack(side="right")

        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

    def _btn(self, parent, text, cmd, primary=False) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=BTN if primary else CARD,
            fg=BTN_FG if primary else FG,
            activebackground="#38bdf8" if primary else "#334155",
            activeforeground=BTN_FG if primary else "#fff",
            relief="flat",
            padx=14,
            pady=6,
            font=("Segoe UI", 10, "bold" if primary else "normal"),
            cursor="hand2",
        )

    def _label(self, parent, text, *, muted=False, bold=False) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            fg=MUTED if muted else FG,
            bg=BG,
            font=("Segoe UI", 9 if muted else 10, "bold" if bold else "normal"),
            justify="left",
            wraplength=500,
            anchor="w",
        )

    def _entry(self, parent, var, *, show: Optional[str] = None) -> tk.Entry:
        e = tk.Entry(
            parent,
            textvariable=var,
            show=show or "",
            bg=CARD,
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Segoe UI", 10),
        )
        e.pack(fill="x", ipady=7)
        return e

    def _cancel(self) -> None:
        self._stop_recording()
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    # --- Connect AI ---

    def _build_connect_tab(self, tab: tk.Frame) -> None:
        pad = tk.Frame(tab, bg=BG)
        pad.pack(fill="both", expand=True, padx=12, pady=10)

        self._label(
            pad,
            "Connect a vision model for maximum accuracy. Keys stay on this PC "
            "(OS keyring when available). Never shipped inside the app binary.",
            muted=True,
        ).pack(anchor="w", pady=(0, 10))

        self._label(pad, "Provider", bold=True).pack(anchor="w")
        labels = [p.label for p in PROVIDERS]
        default = PROVIDERS[0].label
        for p in PROVIDERS:
            if secrets.get_secret(p.secret_name):
                default = p.label
                break
        self.provider_label_var = tk.StringVar(value=default)
        box = ttk.Combobox(
            pad,
            textvariable=self.provider_label_var,
            values=labels,
            state="readonly",
            font=("Segoe UI", 10),
        )
        box.pack(fill="x", pady=(4, 6))
        box.bind("<<ComboboxSelected>>", lambda e: self._on_provider_change())

        self.help_var = tk.StringVar()
        tk.Label(
            pad,
            textvariable=self.help_var,
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        link_row = tk.Frame(pad, bg=BG)
        link_row.pack(fill="x", pady=(0, 8))
        self._btn(link_row, "Open key page in browser", self._open_key_page).pack(side="left")

        self._label(pad, "API key", bold=True).pack(anchor="w", pady=(8, 2))
        self.key_var = tk.StringVar()
        self._key_show = False
        key_row = tk.Frame(pad, bg=BG)
        key_row.pack(fill="x")
        self.key_entry = tk.Entry(
            key_row,
            textvariable=self.key_var,
            show="*",
            bg=CARD,
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Consolas", 10),
        )
        self.key_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.show_btn = tk.Button(
            key_row,
            text="Show",
            command=self._toggle_show_key,
            bg=CARD,
            fg=FG,
            relief="flat",
            padx=8,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self.show_btn.pack(side="left", padx=(6, 0))

        self.key_state_var = tk.StringVar(value="")
        tk.Label(
            pad,
            textvariable=self.key_state_var,
            fg=OK,
            bg=BG,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        self._label(pad, "Model (optional override)", muted=True).pack(anchor="w", pady=(10, 2))
        self.model_var = tk.StringVar(
            value=str(self.config.get("vision_model") or PROVIDERS[0].default_model)
        )
        self._entry(pad, self.model_var)

        action = tk.Frame(pad, bg=BG)
        action.pack(fill="x", pady=(14, 6))
        self.test_btn = self._btn(action, "Test connection", self._test_connection, primary=True)
        self.test_btn.pack(side="left")
        self._btn(action, "Save key", self._save_key_only).pack(side="left", padx=(8, 0))
        self._btn(action, "Remove key", self._remove_key).pack(side="right")

        self.test_result_var = tk.StringVar(value="")
        self.test_result_lbl = tk.Label(
            pad,
            textvariable=self.test_result_var,
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
            anchor="w",
        )
        self.test_result_lbl.pack(fill="x", pady=(8, 0))

        self._label(
            pad,
            "Privacy: only the cropped snip is sent when AI mode is on. "
            "Local OCR never leaves this device.",
            muted=True,
        ).pack(anchor="w", pady=(16, 0))

        self._on_provider_change()

    def _current_provider(self):
        label = self.provider_label_var.get()
        for p in PROVIDERS:
            if p.label == label:
                return p
        return PROVIDERS[0]

    def _on_provider_change(self) -> None:
        p = self._current_provider()
        self.help_var.set(p.help_blurb)
        existing = secrets.get_secret(p.secret_name) or ""
        self.key_var.set("")
        if existing:
            self.key_state_var.set(f"Key on file for {p.short}  (...{existing[-4:]})")
        else:
            self.key_state_var.set(f"No key saved for {p.short} yet")
        cur = self.model_var.get().strip()
        known_defaults = {x.default_model for x in PROVIDERS}
        if not cur or cur in known_defaults:
            self.model_var.set(p.default_model)
        self.test_result_var.set("")
        self.status_var.set(provider_status_line())

    def _toggle_show_key(self) -> None:
        self._key_show = not self._key_show
        self.key_entry.configure(show="" if self._key_show else "*")
        self.show_btn.configure(text="Hide" if self._key_show else "Show")

    def _open_key_page(self) -> None:
        webbrowser.open(self._current_provider().get_key_url)

    def _resolve_key_for_action(self) -> tuple[Optional[str], str]:
        p = self._current_provider()
        pasted = self.key_var.get().strip()
        if pasted and not pasted.startswith("*"):
            return pasted, ""
        stored = secrets.get_secret(p.secret_name)
        if stored:
            return stored, ""
        return None, "Paste an API key first (or save one)."

    def _save_key_only(self) -> None:
        p = self._current_provider()
        pasted = self.key_var.get().strip()
        if not pasted or pasted.startswith("*"):
            messagebox.showinfo(
                "SnipText",
                "Paste a new API key in the field, then click Save key.",
                parent=self.win,
            )
            return
        secrets.set_secret(p.secret_name, pasted)
        self.config["vision_model"] = self.model_var.get().strip() or p.default_model
        if self.config.get("engine_mode") == "local_only":
            self.config["engine_mode"] = "ai_first"
            if hasattr(self, "mode_label_var"):
                self.mode_label_var.set(ENGINE_MODE_LABELS["ai_first"])
        save_config(self.config)
        self.key_var.set("")
        self.key_state_var.set(f"Key saved for {p.short}  (...{pasted[-4:]})")
        self.status_var.set(provider_status_line())
        self.test_result_var.set(f"Saved. Click Test connection to verify {p.short}.")
        self.test_result_lbl.configure(fg=MUTED)
        if self.on_save:
            self.on_save(dict(self.config))

    def _remove_key(self) -> None:
        p = self._current_provider()
        if not secrets.get_secret(p.secret_name):
            messagebox.showinfo("SnipText", f"No {p.short} key on file.", parent=self.win)
            return
        if not messagebox.askyesno(
            "SnipText",
            f"Remove the saved {p.short} API key from this PC?",
            parent=self.win,
        ):
            return
        secrets.set_secret(p.secret_name, "")
        self.key_var.set("")
        self.key_state_var.set(f"No key saved for {p.short} yet")
        self.status_var.set(provider_status_line())
        self.test_result_var.set(f"{p.short} key removed.")
        self.test_result_lbl.configure(fg=MUTED)
        if self.on_save:
            self.on_save(dict(self.config))

    def _test_connection(self) -> None:
        if self._testing:
            return
        key, err = self._resolve_key_for_action()
        if err or not key:
            self.test_result_var.set(err or "No key")
            self.test_result_lbl.configure(fg=DANGER)
            return
        p = self._current_provider()
        model = self.model_var.get().strip() or p.default_model
        self._testing = True
        self.test_btn.configure(state="disabled", text="Testing...")
        self.test_result_var.set(f"Testing {p.short} vision...")
        self.test_result_lbl.configure(fg=MUTED)

        def worker() -> None:
            ok, msg = test_provider_connection(p.id, key, model=model)

            def done() -> None:
                self._testing = False
                self.test_btn.configure(state="normal", text="Test connection")
                self.test_result_var.set(msg)
                self.test_result_lbl.configure(fg=OK if ok else DANGER)
                if ok:
                    pasted = self.key_var.get().strip()
                    if pasted and not pasted.startswith("*"):
                        secrets.set_secret(p.secret_name, pasted)
                        self.key_var.set("")
                        self.key_state_var.set(f"Key saved for {p.short}  (...{pasted[-4:]})")
                    self.config["vision_model"] = model
                    if self.config.get("engine_mode") == "local_only":
                        self.config["engine_mode"] = "ai_first"
                        if hasattr(self, "mode_label_var"):
                            self.mode_label_var.set(ENGINE_MODE_LABELS["ai_first"])
                    save_config(self.config)
                    self.status_var.set(provider_status_line())
                    if self.on_save:
                        self.on_save(dict(self.config))

            try:
                self.win.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=worker, name="sniptext-key-test", daemon=True).start()

    # --- Preferences ---

    def _build_prefs_tab(self, tab: tk.Frame) -> None:
        # Scrollable prefs
        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        pad = tk.Frame(canvas, bg=BG)
        pad.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=pad, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.vars: dict[str, tk.Variable] = {}

        # Hotkey + recorder
        self._label(pad, "Global hotkey", bold=True).pack(anchor="w", padx=12, pady=(10, 2))
        self._label(
            pad,
            "Click Record, then press your shortcut (e.g. Ctrl+Shift+T). Esc cancels.",
            muted=True,
        ).pack(anchor="w", padx=12)
        hk_row = tk.Frame(pad, bg=BG)
        hk_row.pack(fill="x", padx=12, pady=4)
        self.vars["hotkey"] = tk.StringVar(
            value=str(self.config.get("hotkey") or "ctrl+shift+t")
        )
        self.hotkey_entry = tk.Entry(
            hk_row,
            textvariable=self.vars["hotkey"],
            bg=CARD,
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.hotkey_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.record_btn = tk.Button(
            hk_row,
            text="Record",
            command=self._toggle_record_hotkey,
            bg=CARD,
            fg=FG,
            relief="flat",
            padx=12,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.record_btn.pack(side="left", padx=(8, 0))
        self.record_status = tk.StringVar(value="")
        tk.Label(
            pad,
            textvariable=self.record_status,
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12)

        # Delay
        self._label(pad, "Delay before selection overlay", bold=True).pack(
            anchor="w", padx=12, pady=(14, 2)
        )
        self._label(
            pad,
            "Gives you time to open a menu or hover state before the dim overlay appears.",
            muted=True,
        ).pack(anchor="w", padx=12)
        delay = int(self.config.get("snip_delay_sec") or 0)
        if delay not in (0, 1, 2, 3, 5):
            delay = 0
        self.delay_var = tk.StringVar(value=str(delay))
        ttk.Combobox(
            pad,
            textvariable=self.delay_var,
            values=["0", "1", "2", "3", "5"],
            state="readonly",
            width=8,
        ).pack(anchor="w", padx=12, pady=4)
        tk.Label(
            pad,
            text="seconds (0 = instant). Tray also has New snip with 3s delay.",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 8),
        ).pack(anchor="w", padx=12)

        # Engine mode
        self._label(pad, "When to use AI", bold=True).pack(anchor="w", padx=12, pady=(14, 2))
        mode_code = str(self.config.get("engine_mode") or "ai_first")
        self.mode_label_var = tk.StringVar(
            value=ENGINE_MODE_LABELS.get(mode_code, ENGINE_MODE_LABELS["ai_first"])
        )
        ttk.Combobox(
            pad,
            textvariable=self.mode_label_var,
            values=[label for _, label in ENGINE_MODE_CHOICES],
            state="readonly",
            font=("Segoe UI", 10),
        ).pack(fill="x", padx=12)

        self._label(pad, "Output format", bold=True).pack(anchor="w", padx=12, pady=(14, 2))
        self.vars["output_format"] = tk.StringVar(
            value=str(self.config.get("output_format") or "markdown")
        )
        ttk.Combobox(
            pad,
            textvariable=self.vars["output_format"],
            values=["markdown", "plain"],
            state="readonly",
        ).pack(fill="x", padx=12)

        self._label(pad, "Local OCR languages (comma-separated)", bold=True).pack(
            anchor="w", padx=12, pady=(14, 2)
        )
        langs = ",".join(self.config.get("languages") or ["en"])
        self.vars["languages_str"] = tk.StringVar(value=langs)
        e = tk.Entry(
            pad,
            textvariable=self.vars["languages_str"],
            bg=CARD,
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Segoe UI", 10),
        )
        e.pack(fill="x", padx=12, ipady=7)

        # Toggles
        # Prefer live registry state for start_with_windows on Windows
        start_val = (
            is_start_with_windows_enabled()
            if platform.system() == "Windows"
            else bool(self.config.get("start_with_windows", False))
        )
        self.vars["show_preview"] = tk.BooleanVar(
            value=bool(self.config.get("show_preview", True))
        )
        self.vars["notifications"] = tk.BooleanVar(
            value=bool(self.config.get("notifications", True))
        )
        self.vars["shutter_sound"] = tk.BooleanVar(
            value=bool(self.config.get("shutter_sound", True))
        )
        self.vars["copy_image_too"] = tk.BooleanVar(
            value=bool(self.config.get("copy_image_too", False))
        )
        self.vars["start_with_windows"] = tk.BooleanVar(value=start_val)

        for key, label in (
            ("show_preview", "Show editable preview card after snip"),
            ("notifications", "System notifications"),
            ("shutter_sound", "Play camera shutter when a snip is captured"),
            ("copy_image_too", "Also copy cropped image when supported"),
            ("start_with_windows", "Start SnipText when I sign in to Windows"),
        ):
            if key == "start_with_windows" and platform.system() != "Windows":
                continue
            tk.Checkbutton(
                pad,
                text=label,
                variable=self.vars[key],
                bg=BG,
                fg=FG,
                selectcolor=CARD,
                activebackground=BG,
                activeforeground=FG,
                font=("Segoe UI", 10),
                anchor="w",
            ).pack(fill="x", padx=12, pady=3)

        # OCR readiness
        self._label(pad, "Local OCR status", bold=True).pack(anchor="w", padx=12, pady=(16, 2))
        tk.Label(
            pad,
            text=readiness_summary(),
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
            wraplength=500,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 16))

    def _toggle_record_hotkey(self) -> None:
        if self._recording:
            self._stop_recording()
            return
        self._recording = True
        self.record_btn.configure(text="Listening...", bg="#0ea5e9", fg=BTN_FG)
        self.record_status.set("Press a key combination now... (Esc to cancel)")
        self.hotkey_entry.configure(state="disabled")

        try:
            from pynput import keyboard
        except ImportError:
            self.record_status.set("pynput not available - type the hotkey manually.")
            self._recording = False
            self.record_btn.configure(text="Record", bg=CARD, fg=FG)
            self.hotkey_entry.configure(state="normal")
            return

        mods = {"ctrl": False, "alt": False, "shift": False, "cmd": False}

        def on_press(key) -> Optional[bool]:
            try:
                if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                    mods["ctrl"] = True
                    return None
                if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                    mods["alt"] = True
                    return None
                if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                    mods["shift"] = True
                    return None
                if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                    mods["cmd"] = True
                    return None
                if key == keyboard.Key.esc:
                    self.win.after(0, lambda: self._finish_record(None, cancelled=True))
                    return False

                # Resolve character / special key
                name = None
                if hasattr(key, "char") and key.char:
                    name = key.char.lower()
                else:
                    kname = str(key).replace("Key.", "").lower()
                    if kname.startswith("f") and kname[1:].isdigit():
                        name = kname
                    elif kname in ("space", "tab", "enter", "insert", "delete", "home", "end"):
                        name = kname
                    else:
                        name = kname

                if not name or name in ("ctrl", "alt", "shift", "cmd"):
                    return None

                parts = []
                if mods["ctrl"]:
                    parts.append("ctrl")
                if mods["cmd"]:
                    parts.append("cmd")
                if mods["alt"]:
                    parts.append("alt")
                if mods["shift"]:
                    parts.append("shift")
                parts.append(name)
                combo = "+".join(parts)
                self.win.after(0, lambda c=combo: self._finish_record(c))
                return False
            except Exception:
                return False

        def on_release(key) -> None:
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                mods["ctrl"] = False
            if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                mods["alt"] = False
            if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                mods["shift"] = False
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                mods["cmd"] = False

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
        self._record_listener = listener

    def _finish_record(self, combo: Optional[str], cancelled: bool = False) -> None:
        self._stop_recording()
        if cancelled or not combo:
            self.record_status.set("Recording cancelled.")
            return
        norm = normalize_hotkey(combo)
        # Need at least one modifier for global hotkeys
        if "+" not in norm:
            self.record_status.set("Use a modifier (Ctrl/Alt/Shift) + a key.")
            return
        self.vars["hotkey"].set(norm)
        self.record_status.set(f"Recorded: {norm}")

    def _stop_recording(self) -> None:
        self._recording = False
        try:
            if self._record_listener is not None:
                self._record_listener.stop()
        except Exception:
            pass
        self._record_listener = None
        try:
            self.record_btn.configure(text="Record", bg=CARD, fg=FG)
            self.hotkey_entry.configure(state="normal")
        except Exception:
            pass

    def _save(self) -> None:
        self._stop_recording()
        cfg = dict(self.config)
        cfg["hotkey"] = normalize_hotkey(str(self.vars["hotkey"].get()))
        mode_label = self.mode_label_var.get()
        cfg["engine_mode"] = ENGINE_MODE_FROM_LABEL.get(mode_label, "ai_first")
        cfg["vision_model"] = self.model_var.get().strip() or "grok-4.5"
        cfg["output_format"] = str(self.vars["output_format"].get())
        langs = [
            p.strip()
            for p in str(self.vars["languages_str"].get()).split(",")
            if p.strip()
        ]
        cfg["languages"] = langs or ["en"]
        cfg["show_preview"] = bool(self.vars["show_preview"].get())
        cfg["notifications"] = bool(self.vars["notifications"].get())
        cfg["shutter_sound"] = bool(self.vars["shutter_sound"].get())
        cfg["copy_image_too"] = bool(self.vars["copy_image_too"].get())
        try:
            cfg["snip_delay_sec"] = int(self.delay_var.get())
        except ValueError:
            cfg["snip_delay_sec"] = 0
        cfg["first_run_complete"] = True

        # Start with Windows
        if "start_with_windows" in self.vars:
            want = bool(self.vars["start_with_windows"].get())
            cfg["start_with_windows"] = want
            ok, msg = set_start_with_windows(want)
            if not ok:
                messagebox.showwarning("SnipText", msg, parent=self.win)

        pasted = self.key_var.get().strip()
        if pasted and not pasted.startswith("*"):
            p = self._current_provider()
            secrets.set_secret(p.secret_name, pasted)

        try:
            save_config(cfg)
        except Exception as exc:
            messagebox.showerror("SnipText", f"Could not save config: {exc}", parent=self.win)
            return

        if self.on_save:
            self.on_save(cfg)
        messagebox.showinfo("SnipText", "Settings saved.", parent=self.win)
        try:
            self.win.destroy()
        except tk.TclError:
            pass
