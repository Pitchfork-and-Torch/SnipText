"""Regression: plain mode must keep bare underscores in identifiers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sniptext.transcribe.postprocess import maybe_plain


def main() -> None:
    assert maybe_plain("hello_world", False) == "hello_world"
    assert maybe_plain("file_name.txt", False) == "file_name.txt"
    assert maybe_plain("say *bold* once", False) == "say bold once"
    assert maybe_plain("use **strong** and `code`", False) == "use strong and code"
    assert maybe_plain("# Title\nbody", False) == "Title\nbody"
    assert maybe_plain("keep *this*", True) == "keep *this*"
    # Old [*_`]+ path turned hello_world into helloworld.
    assert "_" in maybe_plain("snake_case_id", False)
    assert maybe_plain("see [docs](https://example.com/x) now", False) == "see docs now"
    assert maybe_plain("keep [docs](https://example.com/x)", True) == "keep [docs](https://example.com/x)"
    print("POSTPROCESS OK")


if __name__ == "__main__":
    main()
