"""Clip Desk history: pin, search, delete. Run: py -3 scripts/test_history.py"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sniptext.services import history as hist


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        hist.history_path = lambda: Path(tmp) / "history.json"
        hist.clear_history()
        a = hist.push_history("alpha clip one", "rapid", limit=20)
        b = hist.push_history("beta table row", "grok-4.5", limit=20)
        hist.push_history("gamma code fence", "rapid", limit=20)
        assert hist.set_pinned(a.id, True) is not None
        desk = hist.list_desk("", limit=20)
        assert desk[0].id == a.id and desk[0].pinned
        found = hist.list_desk("table", limit=20)
        assert len(found) == 1 and found[0].id == b.id
        assert hist.delete_item(b.id) is True
        leftover = hist.list_desk("", limit=20)
        assert all(i.id != b.id for i in leftover)
        assert any(i.pinned for i in leftover)

        ledger = Path(tmp) / "ledger.json"
        n = hist.export_ledger(ledger, pinned_only=True)
        assert n == 1
        hist.clear_history()
        hist.push_history("fresh clip", "rapid", limit=20)
        stats = hist.import_ledger(ledger)
        assert stats["added"] == 1
        desk = hist.list_desk("", limit=20)
        assert any(i.pinned and "alpha" in i.text for i in desk)
        pins = hist.list_desk("", limit=20, pinned_only=True)
        assert len(pins) == 1

        # pins survive history_limit overflow; only unpinned recents are evicted
        hist.clear_history()
        keep = hist.push_history("keep me pinned", "rapid", limit=5)
        assert hist.set_pinned(keep.id, True) is not None
        for n in range(8):
            hist.push_history(f"snip {n}", "rapid", limit=5)
        after = hist.load_history(limit=200)
        assert len(after) == 6, [i.text for i in after]
        assert any(i.id == keep.id and i.pinned for i in after)
        assert [i.text for i in after if not i.pinned] == [f"snip {n}" for n in range(7, 2, -1)]

        # re-snipping a pinned text dedupes to one row and keeps the pin
        hist.clear_history()
        dup = hist.push_history("same text", "rapid", limit=5)
        hist.set_pinned(dup.id, True)
        hist.push_history("same text", "grok-4.5", limit=5)
        rows = hist.load_history(limit=200)
        assert len(rows) == 1 and rows[0].pinned

        # pin/delete must not truncate a ledger-grown desk past 200 rows
        hist.clear_history()
        bulk = [
            hist.HistoryItem(
                id=str(i),
                text=f"bulk {i}",
                engine="rapid",
                created_at=float(i),
            )
            for i in range(220)
        ]
        hist.save_history(bulk, limit=220)
        assert len(hist.load_history(limit=500)) == 220
        assert hist.set_pinned("5", True) is not None
        after_pin = hist.load_history(limit=500)
        assert len(after_pin) == 220, len(after_pin)
        assert any(i.id == "5" and i.pinned for i in after_pin)
        assert hist.delete_item("10") is True
        after_del = hist.load_history(limit=500)
        assert len(after_del) == 219
        assert all(i.id != "10" for i in after_del)
        assert any(i.id == "219" for i in after_del)

        hist.last_region_path = lambda: Path(tmp) / "last_region.json"
        hist.save_last_region((10, 20, 300, 80))
        replay = hist.load_last_region()
        assert replay == (10, 20, 300, 80)
        assert hist.rect_from_region({"left": 1, "top": 2, "width": 0, "height": 9}) is None
    print("HISTORY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
