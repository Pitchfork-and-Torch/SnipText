#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -q pyinstaller
python3 -m PyInstaller \
  --noconfirm --clean --onedir --windowed \
  --name SnipText \
  --paths "$ROOT" \
  --add-data "assets:assets" \
  --hidden-import sniptext \
  sniptext/__main__.py
echo "Output: $ROOT/dist/SnipText"
