"""Floating editable preview card after a snip."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Optional

from PIL import Image

from sniptext.services import clipboard


class PreviewCard:
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        engine: str,
        image: Optional[Image.Image] = None,
        *,
        auto_dismiss_sec: int = 8,
        on_reprocess_local: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.image = image
        self.on_reprocess_local = on_reprocess_local
        self._closed = False

        self.win = tk.Toplevel(parent)
        self.win.title("SnipText")
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#0f172a")
        self.win.geometry("420x280+80+80")
        try:
            self.win.attributes("-alpha", 0.97)
        except tk.TclError:
            pass

        header = tk.Frame(self.win, bg="#0f172a")
        header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(
            header,
            text="Text copied",
            fg="#5BDBFF",
            bg="#0f172a",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")
        engine_labels = {
            "xai_vision": "xAI Grok",
            "openai_vision": "OpenAI",
            "anthropic_vision": "Anthropic",
            "google_vision": "Google",
            "rapid": "RapidOCR (local)",
            "paddle": "PaddleOCR (local)",
            "easyocr": "EasyOCR (local)",
            "tesseract": "Tesseract (local)",
        }
        nice = engine_labels.get(engine, engine)
        tk.Label(
            header,
            text=f"via {nice}",
            fg="#94a3b8",
            bg="#0f172a",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 0))

        self.text = tk.Text(
            self.win,
            wrap="word",
            bg="#1e293b",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            font=("Consolas", 10),
            padx=8,
            pady=8,
        )
        self.text.pack(fill="both", expand=True, padx=12, pady=6)
        self.text.insert("1.0", text or "")

        btns = tk.Frame(self.win, bg="#0f172a")
        btns.pack(fill="x", padx=12, pady=(0, 12))

        def btn(label: str, cmd, side="left") -> None:
            b = tk.Button(
                btns,
                text=label,
                command=cmd,
                bg="#1e293b",
                fg="#e2e8f0",
                activebackground="#334155",
                activeforeground="#fff",
                relief="flat",
                padx=10,
                pady=4,
                font=("Segoe UI", 9),
            )
            b.pack(side=side, padx=(0, 6))

        btn("Copy again", self._copy)
        if on_reprocess_local:
            btn("Re-process local", self._reprocess)
        btn("Save image", self._save_image)
        btn("Close", self.close, side="right")

        self.win.bind("<Escape>", lambda e: self.close())
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        if auto_dismiss_sec and auto_dismiss_sec > 0:
            self.win.after(int(auto_dismiss_sec * 1000), self.close)

    def _copy(self) -> None:
        clipboard.set_text(self.text.get("1.0", "end-1c"))

    def _reprocess(self) -> None:
        if self.on_reprocess_local:
            self.on_reprocess_local()

    def _save_image(self) -> None:
        if self.image is None:
            messagebox.showinfo("SnipText", "No image available for this snip.", parent=self.win)
            return
        path = filedialog.asksaveasfilename(
            parent=self.win,
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
            title="Save snip image",
        )
        if path:
            try:
                self.image.save(path)
            except Exception as exc:
                messagebox.showerror("SnipText", f"Save failed: {exc}", parent=self.win)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.win.destroy()
        except tk.TclError:
            pass
