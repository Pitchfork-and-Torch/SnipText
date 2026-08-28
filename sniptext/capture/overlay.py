"""Fullscreen multi-monitor region selection overlay.

One topmost borderless window per monitor. Coordinates are virtual-desktop
absolute (mss space). Returns (left, top, width, height) or None if cancelled.

Prefer select_region(parent=app_root) so overlays share the app Tk loop.
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable, List, Optional, Tuple

from sniptext.capture.monitors import MonitorInfo, list_monitors

Rect = Tuple[int, int, int, int]

DIM_COLOR = "#0b1220"
BORDER_COLOR = "#5BDBFF"
BORDER_WIDTH = 2
TOOLTIP_BG = "#111827"
TOOLTIP_FG = "#F9FAFB"
MIN_SIZE = 4


class _MonitorOverlay:
    def __init__(
        self,
        parent: tk.Misc,
        mon: MonitorInfo,
        on_result: Callable[[Optional[Rect]], None],
        shared: dict,
    ) -> None:
        self.mon = mon
        self.on_result = on_result
        self.shared = shared
        self.start: Optional[Tuple[int, int]] = None
        self.rect_id = None
        self.tip_ids: list = []

        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            # Dim the whole screen; selection "hole" is drawn with stipple trick
            self.win.attributes("-alpha", 0.40)
        except tk.TclError:
            pass
        self.win.configure(bg=DIM_COLOR)
        self.win.geometry(f"{mon.width}x{mon.height}+{mon.left}+{mon.top}")

        self.canvas = tk.Canvas(
            self.win,
            width=mon.width,
            height=mon.height,
            highlightthickness=0,
            bg=DIM_COLOR,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda e: self._cancel())
        self.canvas.bind("<Escape>", lambda e: self._cancel())
        self.win.bind("<KeyPress-Escape>", lambda e: self._cancel())

        try:
            self.win.focus_force()
            self.canvas.focus_set()
        except tk.TclError:
            pass

    def _to_abs(self, lx: int, ly: int) -> Tuple[int, int]:
        return self.mon.left + int(lx), self.mon.top + int(ly)

    def _to_local(self, ax: int, ay: int) -> Tuple[int, int]:
        return ax - self.mon.left, ay - self.mon.top

    def _press(self, event: tk.Event) -> None:
        if self.shared.get("done"):
            return
        ax, ay = self._to_abs(event.x, event.y)
        self.start = (ax, ay)
        self.shared["start"] = self.start
        self._clear_draw()

    def _drag(self, event: tk.Event) -> None:
        if self.shared.get("done") or not self.start:
            return
        ax, ay = self._to_abs(event.x, event.y)
        self._draw_selection(self.start[0], self.start[1], ax, ay)

    def _release(self, event: tk.Event) -> None:
        if self.shared.get("done") or not self.start:
            return
        ax, ay = self._to_abs(event.x, event.y)
        x0, y0 = self.start
        left = min(x0, ax)
        top = min(y0, ay)
        width = abs(ax - x0)
        height = abs(ay - y0)
        if width < MIN_SIZE or height < MIN_SIZE:
            self._clear_draw()
            self.start = None
            return
        self.shared["done"] = True
        self.on_result((left, top, width, height))

    def _cancel(self) -> None:
        if self.shared.get("done"):
            return
        self.shared["done"] = True
        self.on_result(None)

    def _clear_draw(self) -> None:
        if self.rect_id is not None:
            try:
                self.canvas.delete(self.rect_id)
            except tk.TclError:
                pass
            self.rect_id = None
        for tid in self.tip_ids:
            try:
                self.canvas.delete(tid)
            except tk.TclError:
                pass
        self.tip_ids = []

    def _draw_selection(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self._clear_draw()
        lx0, ly0 = self._to_local(x0, y0)
        lx1, ly1 = self._to_local(x1, y1)
        # Brighter inner area approximation: draw border only on dim window
        self.rect_id = self.canvas.create_rectangle(
            lx0,
            ly0,
            lx1,
            ly1,
            outline=BORDER_COLOR,
            width=BORDER_WIDTH,
        )
        w, h = abs(x1 - x0), abs(y1 - y0)
        label = f"{w} x {h}"
        tx = min(lx0, lx1) + 8
        ty = min(ly0, ly1) - 24
        if ty < 4:
            ty = min(ly0, ly1) + 10
        text_id = self.canvas.create_text(
            tx,
            ty,
            text=label,
            anchor="nw",
            fill=TOOLTIP_FG,
            font=("Segoe UI", 10, "bold"),
        )
        bbox = self.canvas.bbox(text_id)
        if bbox:
            pad = 4
            bg = self.canvas.create_rectangle(
                bbox[0] - pad,
                bbox[1] - pad,
                bbox[2] + pad,
                bbox[3] + pad,
                fill=TOOLTIP_BG,
                outline=BORDER_COLOR,
            )
            self.canvas.tag_lower(bg, text_id)
            self.tip_ids.extend([bg, text_id])
        else:
            self.tip_ids.append(text_id)

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def select_region(parent: Optional[tk.Misc] = None) -> Optional[Rect]:
    """
    Block until user selects a region or cancels.
    When parent is provided, overlays attach to that Tk and use wait_variable.
    """
    owns_root = parent is None
    if owns_root:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except tk.TclError:
            pass
        parent = root
    else:
        root = parent.winfo_toplevel()

    monitors = list_monitors()
    if not monitors:
        if owns_root:
            try:
                root.destroy()
            except tk.TclError:
                pass
        return None

    result_holder: dict = {"rect": None}
    done_var = tk.BooleanVar(master=root, value=False)
    shared: dict = {"done": False, "start": None}
    overlays: List[_MonitorOverlay] = []

    def finish(rect: Optional[Rect]) -> None:
        if shared.get("finishing"):
            return
        shared["finishing"] = True
        shared["done"] = True
        result_holder["rect"] = rect
        for ov in overlays:
            ov.destroy()
        try:
            done_var.set(True)
        except tk.TclError:
            pass
        if owns_root:
            try:
                root.quit()
            except tk.TclError:
                pass

    for mon in monitors:
        overlays.append(_MonitorOverlay(parent, mon, finish, shared))

    def on_escape(_event=None) -> None:
        finish(None)

    try:
        root.bind_all("<Escape>", on_escape)
    except tk.TclError:
        pass

    try:
        overlays[0].win.lift()
        overlays[0].win.focus_force()
    except Exception:
        pass

    if owns_root:
        root.mainloop()
        try:
            root.destroy()
        except tk.TclError:
            pass
    else:
        try:
            root.wait_variable(done_var)
        except tk.TclError:
            pass
        try:
            root.unbind_all("<Escape>")
        except tk.TclError:
            pass

    return result_holder["rect"]
