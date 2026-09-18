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
    assert maybe_plain("was ~~old~~ now", False) == "was old now"
    # Nested parens in the URL must not leave a trailing ")".
    assert (
        maybe_plain(
            "see [wiki](https://en.wikipedia.org/wiki/Face_(disambiguation)) now",
            False,
        )
        == "see wiki now"
    )
    assert maybe_plain("go [lab](https://example.com/a_(b)) x", False) == "go lab x"
    assert maybe_plain("keep ~~marked~~", True) == "keep ~~marked~~"
    assert (
        maybe_plain("see <https://example.com/x> now", False)
        == "see https://example.com/x now"
    )
    assert maybe_plain("see <https://example.com/x>", True) == "see <https://example.com/x>"
    assert (
        maybe_plain("mail me <user@example.com> please", False)
        == "mail me user@example.com please"
    )
    assert maybe_plain("mail me <user@example.com>", True) == "mail me <user@example.com>"
    assert (
        maybe_plain("see <HTTPS://Example.COM/Path> now", False)
        == "see HTTPS://Example.COM/Path now"
    )

    assert (
        maybe_plain("mail me <mailto:user@example.com> please", False)
        == "mail me user@example.com please"
    )
    assert (
        maybe_plain("mail me <MAILTO:user@example.com> please", False)
        == "mail me user@example.com please"
    )
    assert maybe_plain("mail me <mailto:user@example.com>", True) == "mail me <mailto:user@example.com>"
    print("POSTPROCESS OK")


if __name__ == "__main__":
    main()
