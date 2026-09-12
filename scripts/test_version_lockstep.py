"""Lock public version stamps to sniptext.__version__. Run: py -3 scripts/test_version_lockstep.py"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sniptext import __version__


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__

    pyproject = _read("pyproject.toml")
    assert f'version = "{__version__}"' in pyproject, "pyproject.toml version drift"

    readme = _read("README.md")
    assert f"version-{__version__}" in readme, "README badge drift"
    assert f"v{__version__} Replay" in readme, "README current package drift"

    html = _read("landing/public/index.html")
    assert f"SnipText {__version__} Replay" in html, "landing title drift"
    assert f'"softwareVersion": "{__version__}"' in html, "JSON-LD softwareVersion drift"
    assert f"{__version__} Replay · Pitchfork-and-Torch" in html, "eyebrow drift"
    assert f"og.jpg?v={__version__}" in html, "OG cache-bust drift"
    assert "signed-ready" not in html, "unsigned EXE must not claim signed-ready"
    assert "Nothing is uploaded." not in html, "product-wide no-upload claim"

    llms = _read("landing/public/llms.txt")
    assert f"Version: {__version__} Replay" in llms, "llms.txt version drift"
    root_llms = _read("llms.txt")
    assert f"Version: {__version__} Replay" in root_llms, "repo-root llms.txt version drift"

    sitemap = _read("landing/public/sitemap.xml")
    assert f"SnipText {__version__} Replay" in sitemap, "sitemap title drift"
    assert f"og.jpg?v={__version__}" in sitemap, "sitemap OG cache-bust drift"

    example = json.loads(_read("config.example.json"))
    assert example["history_limit"] == 50, "config.example history_limit != default 50"
    assert example["shutter_sound"] is True, "config.example missing shutter_sound"
    assert example.get("replay_hotkey") == "ctrl+shift+r", "config.example missing replay_hotkey"

    print(f"LOCKSTEP OK {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
