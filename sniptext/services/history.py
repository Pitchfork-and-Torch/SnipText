"""Recent transcription history (local JSON only)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from sniptext.services.config import history_path


def last_region_path() -> Path:
    return history_path().parent / "last_region.json"


def region_from_rect(rect: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, width, height = rect
    return {
        "left": int(left),
        "top": int(top),
        "width": int(width),
        "height": int(height),
    }


def rect_from_region(data: Any) -> Optional[tuple[int, int, int, int]]:
    if not isinstance(data, dict):
        return None
    try:
        left = int(data["left"])
        top = int(data["top"])
        width = int(data["width"])
        height = int(data["height"])
    except (KeyError, TypeError, ValueError):
        return None
    if width < 1 or height < 1:
        return None
    return (left, top, width, height)


def save_last_region(rect: tuple[int, int, int, int]) -> None:
    path = last_region_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = region_from_rect(rect)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_last_region() -> Optional[tuple[int, int, int, int]]:
    path = last_region_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return rect_from_region(data)


@dataclass
class HistoryItem:
    id: str
    text: str
    engine: str
    created_at: float
    preview: str = ""
    pinned: bool = False

    def __post_init__(self) -> None:
        if not self.preview:
            one_line = " ".join((self.text or "").split())
            self.preview = one_line[:80] + ("..." if len(one_line) > 80 else "")


def load_history(limit: int = 15) -> list[HistoryItem]:
    path = history_path()
    if not path.is_file():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items: list[HistoryItem] = []
        if isinstance(data, list):
            for row in data[:limit]:
                if not isinstance(row, dict):
                    continue
                items.append(
                    HistoryItem(
                        id=str(row.get("id") or uuid.uuid4()),
                        text=str(row.get("text") or ""),
                        engine=str(row.get("engine") or "unknown"),
                        created_at=float(row.get("created_at") or 0),
                        preview=str(row.get("preview") or ""),
                        pinned=bool(row.get("pinned")),
                    )
                )
        return items
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []


def save_history(items: list[HistoryItem], limit: int = 15) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(i) for i in items[:limit]]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def push_history(text: str, engine: str, limit: int = 15) -> HistoryItem:
    items = load_history(limit=limit * 2)
    item = HistoryItem(
        id=str(uuid.uuid4()),
        text=text,
        engine=engine,
        created_at=time.time(),
    )
    items.insert(0, item)
    # drop empties / dedupe consecutive identical
    cleaned: list[HistoryItem] = []
    for it in items:
        if not (it.text or "").strip():
            continue
        if cleaned and cleaned[-1].text == it.text:
            continue
        cleaned.append(it)
    save_history(cleaned[:limit], limit=limit)
    return item


def clear_history() -> None:
    path = history_path()
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            save_history([], limit=0)


def search_history(query: str, limit: int = 15) -> list[HistoryItem]:
    q = (query or "").strip().lower()
    items = load_history(limit=200)
    if not q:
        return items[:limit]
    return [i for i in items if q in i.text.lower() or q in i.engine.lower()][:limit]


def list_desk(
    query: str = "",
    limit: int = 50,
    pinned_only: bool = False,
) -> list[HistoryItem]:
    """Pinned first, then recents. Used by Clip Desk."""
    items = search_history(query, limit=200)
    pinned = [i for i in items if i.pinned]
    if pinned_only:
        return pinned[:limit]
    rest = [i for i in items if not i.pinned]
    return (pinned + rest)[:limit]


LEDGER_KIND = "clip-desk-ledger"
LEDGER_LIMIT = 200


def export_ledger(
    path: Path,
    query: str = "",
    pinned_only: bool = False,
) -> int:
    """Write a local JSON ledger. Never includes images."""
    items = list_desk(query, limit=LEDGER_LIMIT, pinned_only=pinned_only)
    payload = {
        "version": 1,
        "app": "sniptext",
        "kind": LEDGER_KIND,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "items": [asdict(i) for i in items],
    }
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(items)


def import_ledger(path: Path) -> dict[str, int]:
    """Merge a local JSON ledger into this machine's desk."""
    src = Path(path)
    raw = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        rows = raw.get("items")
    elif isinstance(raw, list):
        rows = raw
    else:
        rows = []
    if not isinstance(rows, list):
        return {"added": 0, "updated": 0, "skipped": 0}

    existing = load_history(limit=LEDGER_LIMIT)
    by_id = {i.id: i for i in existing}
    by_text = {(i.text or "").strip(): i for i in existing if (i.text or "").strip()}
    added = 0
    updated = 0
    skipped = 0

    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            skipped += 1
            continue
        incoming = HistoryItem(
            id=str(row.get("id") or uuid.uuid4()),
            text=text,
            engine=str(row.get("engine") or "import"),
            created_at=float(row.get("created_at") or time.time()),
            preview=str(row.get("preview") or ""),
            pinned=bool(row.get("pinned")),
        )
        hit = by_id.get(incoming.id) or by_text.get(text)
        if hit is None:
            existing.insert(0, incoming)
            by_id[incoming.id] = incoming
            by_text[text] = incoming
            added += 1
            continue
        changed = False
        if incoming.pinned and not hit.pinned:
            hit.pinned = True
            changed = True
        if incoming.text and incoming.text != hit.text:
            hit.text = incoming.text
            hit.preview = ""
            hit.__post_init__()
            changed = True
        if changed:
            updated += 1
        else:
            skipped += 1

    save_history(existing, limit=max(len(existing), LEDGER_LIMIT))
    return {"added": added, "updated": updated, "skipped": skipped}


def set_pinned(item_id: str, pinned: bool) -> Optional[HistoryItem]:
    items = load_history(limit=200)
    hit = None
    for it in items:
        if it.id == item_id:
            it.pinned = bool(pinned)
            hit = it
            break
    if hit is None:
        return None
    save_history(items, limit=max(len(items), 50))
    return hit


def delete_item(item_id: str) -> bool:
    items = load_history(limit=200)
    next_items = [i for i in items if i.id != item_id]
    if len(next_items) == len(items):
        return False
    save_history(next_items, limit=max(len(next_items), 1))
    return True
