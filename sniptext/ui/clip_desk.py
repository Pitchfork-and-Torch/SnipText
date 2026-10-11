"""Clip Desk - searchable, pin-able snip history window."""

from __future__ import annotations

import json
import time
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Optional

from sniptext.services import clipboard
from sniptext.services.history import (
    HistoryItem,
    delete_item,
    export_ledger,
    import_ledger,
    list_desk,
    set_pinned,
)

BG = "#0f172a"
CARD = "#1e293b"
FG = "#e2e8f0"
MUTED = "#94a3b8"
ACCENT = "#5BDBFF"
BTN = "#0ea5e9"
BTN_FG = "#0f172a"
DANGER = "#f87171"


def _when(ts: float) -> str:
    if not ts:
        return ""
    return time.strftime("%H:%M", time.localtime(ts))


class ClipDesk:
    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.on_change = on_change
        self._items: list[HistoryItem] = []
        self.pinned_only = False

        self.win = tk.Toplevel(parent)
        self.win.title("SnipText - Clip Desk")
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.win.configure(bg=BG)
        self.win.geometry("560x520+120+60")
        self.win.minsize(420, 360)

        head = tk.Frame(self.win, bg=BG)
        head.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(
            head,
            text="Clip Desk",
            fg=ACCENT,
            bg=BG,
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        tk.Label(
            head,
            text="Pinned snips stay on this machine",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
        ).pack(side="right")

        search_row = tk.Frame(self.win, bg=BG)
        search_row.pack(fill="x", padx=16, pady=(4, 8))
        tk.Label(search_row, text="/", fg=ACCENT, bg=BG, font=("Segoe UI", 11)).pack(
            side="left", padx=(0, 8)
        )
        self.query = tk.StringVar()
        entry = tk.Entry(
            search_row,
            textvariable=self.query,
            bg=CARD,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=("Segoe UI", 11),
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        entry.bind("<KeyRelease>", lambda _e: self.refresh())
        entry.bind("<Return>", lambda _e: self.copy_selected())
        entry.focus_set()

        self.listbox = tk.Listbox(
            self.win,
            bg=CARD,
            fg=FG,
            selectbackground="#164e63",
            selectforeground=FG,
            relief="flat",
            highlightthickness=0,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.listbox.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.listbox.bind("<Double-Button-1>", lambda _e: self.copy_selected())
        self.listbox.bind("<Return>", lambda _e: self.copy_selected())

        self.status = tk.StringVar(value="")
        tk.Label(
            self.win,
            textvariable=self.status,
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", padx=16)

        btns = tk.Frame(self.win, bg=BG)
        btns.pack(fill="x", padx=16, pady=(6, 14))
        self._btn(btns, "Copy", self.copy_selected, BTN, BTN_FG).pack(side="left")
        self._btn(btns, "Pin", self.pin_selected, CARD, ACCENT).pack(
            side="left", padx=(8, 0)
        )
        self._btn(btns, "Unpin", self.unpin_selected, CARD, MUTED).pack(
            side="left", padx=(8, 0)
        )
        self.filter_btn = self._btn(btns, "Pinned only", self.toggle_pinned_only, CARD, MUTED)
        self.filter_btn.pack(side="left", padx=(8, 0))
        self._btn(btns, "Remove", self.remove_selected, CARD, DANGER).pack(
            side="right"
        )

        ledger = tk.Frame(self.win, bg=BG)
        ledger.pack(fill="x", padx=16, pady=(0, 14))
        self._btn(ledger, "Export ledger", self.export_desk, CARD, ACCENT).pack(side="left")
        self._btn(ledger, "Import ledger", self.import_desk, CARD, MUTED).pack(
            side="left", padx=(8, 0)
        )
        self._btn(ledger, "Copy pinned", self.copy_pinned, CARD, MUTED).pack(side="left", padx=(8, 0))

        self.win.bind("<Escape>", lambda _e: self.win.destroy())
        self.refresh()

    def _btn(self, parent: tk.Misc, label: str, cmd, bg: str, fg: str) -> tk.Button:
        return tk.Button(
            parent,
            text=label,
            command=cmd,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="flat",
            padx=12,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )

    def _selected(self) -> Optional[HistoryItem]:
        sel = self.listbox.curselection()
        if not sel:
            return None
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._items):
            return None
        return self._items[idx]

    def refresh(self) -> None:
        q = self.query.get()
        self._items = list_desk(q, limit=50, pinned_only=self.pinned_only)
        self.listbox.delete(0, tk.END)
        if not self._items:
            self.listbox.insert(0, "  Clip Desk is empty. Snip something first.")
            self.status.set("0 snips")
            return
        for it in self._items:
            mark = "*" if it.pinned else " "
            preview = (it.preview or it.text).replace("\n", " ")[:64]
            line = f"{mark}  {preview}   {_when(it.created_at)}  {it.engine}"
            self.listbox.insert(tk.END, line)
        pinned_n = sum(1 for i in self._items if i.pinned)
        scope = "pinned" if self.pinned_only else "desk"
        self.status.set(
            f"{len(self._items)} {scope}  ·  {pinned_n} pinned  ·  local only"
        )

    def copy_selected(self) -> None:
        item = self._selected()
        if not item or not item.text:
            return
        clipboard.set_text(item.text)
        self.status.set("Copied to clipboard")

    def pin_selected(self) -> None:
        item = self._selected()
        if not item:
            return
        set_pinned(item.id, True)
        self.refresh()
        if self.on_change:
            self.on_change()

    def unpin_selected(self) -> None:
        item = self._selected()
        if not item:
            return
        set_pinned(item.id, False)
        self.refresh()
        if self.on_change:
            self.on_change()

    def remove_selected(self) -> None:
        item = self._selected()
        if not item:
            return
        delete_item(item.id)
        self.refresh()
        if self.on_change:
            self.on_change()

    def toggle_pinned_only(self) -> None:
        self.pinned_only = not self.pinned_only
        self.filter_btn.configure(
            fg=ACCENT if self.pinned_only else MUTED,
            text="Pinned only" if not self.pinned_only else "Show all",
        )
        self.refresh()

    def copy_pinned(self) -> None:
        pins = [i.text for i in list_desk("", limit=200, pinned_only=True) if i.text]
        if not pins:
            self.status.set("No pinned snips")
            return
        clipboard.set_text("\n\n".join(pins))
        self.status.set(f"Copied {len(pins)} pinned snips")

    def export_desk(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Export Clip Desk ledger",
            defaultextension=".json",
            filetypes=[("JSON ledger", "*.json"), ("All files", "*.*")],
            initialfile="sniptext-ledger.json",
        )
        if not path:
            return
        n = export_ledger(path, query=self.query.get(), pinned_only=self.pinned_only)
        self.status.set(f"Exported {n} snips")

    def import_desk(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.win,
            title="Import Clip Desk ledger",
            filetypes=[("JSON ledger", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            stats = import_ledger(path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self.status.set("Import failed")
            return
        self.refresh()
        if self.on_change:
            self.on_change()
        self.status.set(
            f"Imported +{stats['added']}  updated {stats['updated']}  skipped {stats['skipped']}"
        )
