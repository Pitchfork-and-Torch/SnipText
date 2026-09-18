"""EasyOCR local engine (optional secondary)."""

from __future__ import annotations

from typing import Any

from PIL import Image
import numpy as np

from sniptext.transcribe.base import TranscriptResult
from sniptext.transcribe.postprocess import clean_ocr_output
from sniptext.transcribe.preprocess import prepare_for_ocr

_reader: Any = None
_failed = False
_langs_loaded: tuple[str, ...] = ()


def _get_reader(languages: list[str]) -> Any:
    global _reader, _failed, _langs_loaded
    if _failed:
        return None
    langs = tuple(languages or ["en"])
    if _reader is not None and _langs_loaded == langs:
        return _reader
    try:
        import easyocr

        _reader = easyocr.Reader(list(langs), gpu=False)
        _langs_loaded = langs
        return _reader
    except Exception:
        _failed = True
        return None


class EasyOCRTranscriber:
    name = "easyocr"

    def available(self) -> bool:
        try:
            import easyocr  # noqa: F401

            return True
        except ImportError:
            return False

    def transcribe(
        self,
        image: Image.Image,
        *,
        languages: list[str],
        prefer_markdown: bool = True,
    ) -> TranscriptResult:
        reader = _get_reader(languages or ["en"])
        if reader is None:
            return TranscriptResult(
                text="",
                engine=self.name,
                error="EasyOCR not installed (pip install easyocr)",
            )
        try:
            prepared = prepare_for_ocr(image, for_vision=False)
            arr = np.array(prepared)
            result = reader.readtext(arr)
            lines = [str(item[1]) for item in result if item and len(item) >= 2]
            scores = [float(item[2]) for item in result if item and len(item) >= 3]
            text = clean_ocr_output("\n".join(lines))
            conf = sum(scores) / len(scores) if scores else None
            return TranscriptResult(text=text, engine=self.name, confidence=conf, format="plain")
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
