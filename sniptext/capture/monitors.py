"""Multi-monitor enumeration using mss (virtual desktop coords)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import mss


@dataclass(frozen=True)
class MonitorInfo:
    index: int  # 1-based mss index
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


def list_monitors() -> List[MonitorInfo]:
    with mss.mss() as sct:
        # monitors[0] is the virtual combined desktop
        out: list[MonitorInfo] = []
        for i, mon in enumerate(sct.monitors[1:], start=1):
            out.append(
                MonitorInfo(
                    index=i,
                    left=int(mon["left"]),
                    top=int(mon["top"]),
                    width=int(mon["width"]),
                    height=int(mon["height"]),
                )
            )
        return out


def virtual_desktop_bounds() -> tuple[int, int, int, int]:
    """Return left, top, width, height of the virtual desktop."""
    with mss.mss() as sct:
        m = sct.monitors[0]
        return int(m["left"]), int(m["top"]), int(m["width"]), int(m["height"])
