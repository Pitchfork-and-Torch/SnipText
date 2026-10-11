"""Keyring success must drop the file copy. Run: py -3 scripts/test_secrets.py"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sniptext.services import secrets


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "secrets.json"
        secrets.secrets_file = lambda: path
        secrets._FILE_WARNING_SHOWN = True
        path.write_text(
            json.dumps({"xai_api_key": "fake-file-value", "openai_api_key": "fake-keep"}) + "\n",
            encoding="utf-8",
        )

        secrets._keyring_set = lambda name, value: True
        secrets.set_secret("xai_api_key", "fake-keyring-value")
        kept = json.loads(path.read_text(encoding="utf-8"))
        assert "xai_api_key" not in kept
        assert kept["openai_api_key"] == "fake-keep"
        assert "fake-keyring-value" not in path.read_text(encoding="utf-8")

        secrets.set_secret("openai_api_key", "fake-keyring-value")
        assert not path.exists()

        secrets._keyring_set = lambda name, value: False
        secrets._FILE_WARNING_SHOWN = True
        secrets.set_secret("google_api_key", "fake-file-only")
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["google_api_key"] == "fake-file-only"
    print("secrets ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
