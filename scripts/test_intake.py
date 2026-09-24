"""Read Image intake: region commit, hotkey clash, in-memory images. No audio. No clipboard steal."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from sniptext.services import history as hist
from sniptext.services.hotkey import assign_hotkeys
from sniptext.services.image_in import (
    dib_from_image,
    image_from_clipboard_payloads,
    image_from_dib,
    load_image_file,
)
from sniptext.services.shutter import play_shutter
from sniptext.transcribe.postprocess import shape_output


def _sample() -> Image.Image:
    img = Image.new("RGB", (2, 2), (10, 20, 30))
    img.putpixel((1, 0), (1, 2, 3))
    return img


def main() -> int:
    sample = _sample()

    assert hist.region_to_store((9, 9, 9, 9), captured=False) is None
    assert hist.region_to_store((1, 2, 0, 4), captured=True) is None
    assert hist.region_to_store((4, 5, 6, 7), captured=True) == (4, 5, 6, 7)

    with tempfile.TemporaryDirectory() as tmp:
        region_file = Path(tmp) / "last_region.json"
        hist.last_region_path = lambda: region_file
        hist.save_last_region((1, 2, 30, 40))
        assert hist.load_last_region() == (1, 2, 30, 40)
        assert not region_file.with_name(region_file.name + ".tmp").exists()
        # A failed grab must not replace the stored region.
        assert hist.region_to_store((8, 8, 8, 8), captured=False) is None
        assert hist.load_last_region() == (1, 2, 30, 40)
        hist.save_last_region((5, 6, 7, 8))
        assert hist.load_last_region() == (5, 6, 7, 8)
        text = region_file.read_text(encoding="utf-8")
        assert "image" not in text
        assert "png" not in text.lower()

        hist.history_path = lambda: Path(tmp) / "history.json"
        hist.clear_history()
        hist.push_history("only text", "rapid", limit=5)
        row = hist.load_history(limit=5)[0]
        assert set(row.__dataclass_fields__) == {
            "id",
            "text",
            "engine",
            "created_at",
            "preview",
            "pinned",
        }
        ledger = Path(tmp) / "ledger.json"
        hist.export_ledger(ledger)
        body = ledger.read_text(encoding="utf-8")
        assert "image" not in body

        png = Path(tmp) / "shot.png"
        sample.save(png, "PNG")
        loaded = load_image_file(png)
        assert loaded.size == (2, 2)
        assert loaded.getpixel((1, 0)) == (1, 2, 3)
        junk = Path(tmp) / "notes.txt"
        junk.write_text("not an image", encoding="utf-8")
        try:
            load_image_file(junk)
        except ValueError as exc:
            assert "notes.txt" in str(exc)
            assert str(tmp) not in str(exc)
        else:
            raise SystemExit("text file must not load as an image")

    buf = io.BytesIO()
    sample.save(buf, "BMP")
    dib = buf.getvalue()[14:]
    back = image_from_dib(dib)
    assert back.size == (2, 2)
    assert back.getpixel((0, 0)) == (10, 20, 30)
    assert back.getpixel((1, 0)) == (1, 2, 3)

    png_buf = io.BytesIO()
    sample.save(png_buf, "PNG")
    via_png = image_from_clipboard_payloads(png_buf.getvalue(), None)
    assert via_png is not None and via_png.getpixel((1, 0)) == (1, 2, 3)
    via_dib = image_from_clipboard_payloads(None, dib_from_image(sample))
    assert via_dib is not None and via_dib.getpixel((0, 0)) == (10, 20, 30)
    assert image_from_clipboard_payloads(None, None) is None
    assert image_from_clipboard_payloads(b"not-png", b"not-dib") is None

    mapping, dropped = assign_hotkeys(
        [
            ("ctrl+shift+t", lambda: None),
            ("ctrl+shift+r", lambda: None),
            ("Ctrl+Shift+R", lambda: None),
            ("r", lambda: None),
            ("ctrl+shift+i", lambda: None),
        ]
    )
    assert dropped == ["Ctrl+Shift+R", "r"]
    assert len(mapping) == 3
    assert "<ctrl>+<shift>+t" in mapping
    assert "<ctrl>+<shift>+r" in mapping
    assert "<ctrl>+<shift>+i" in mapping

    assert shape_output("a  b\nc", "line") == "a b c"
    assert shape_output("**bold**\nnext", "line") == "bold next"
    assert shape_output("**bold**", "plain") == "bold"
    assert shape_output("**bold**", "markdown") == "**bold**"

    calls: list[str] = []
    assert play_shutter(False, player=lambda p: calls.append(p)) is False
    assert calls == []
    assert play_shutter(True, player=lambda p: calls.append("played")) is True
    assert calls == ["played"]

    print("INTAKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
