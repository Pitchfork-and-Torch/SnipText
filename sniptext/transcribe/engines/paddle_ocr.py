"""PaddleOCR local engine (optional; best accuracy when available)."""

from __future__ import annotations

from typing import Any, Optional

from PIL import Image
import numpy as np

from sniptext.transcribe.base import TranscriptResult
from sniptext.transcribe.postprocess import clean_ocr_output
from sniptext.transcribe.preprocess import prepare_for_ocr

_ocr: Any = None
_failed = False


def _get_ocr(lang: str = "en") -> Any:
    global _ocr, _failed
    if _failed:
        return None
    if _ocr is not None:
        return _ocr
    try:
        from paddleocr import PaddleOCR

        # use_angle_cls for rotated UI text; show_log varies by version
        try:
            _ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        except TypeError:
            _ocr = PaddleOCR(use_angle_cls=True, lang=lang)
        return _ocr
    except Exception:
        _failed = True
        return None


class PaddleOCRTranscriber:
    name = "paddle"

    def available(self) -> bool:
        return _get_ocr() is not None

    def transcribe(
        self,
        image: Image.Image,
        *,
        languages: list[str],
        prefer_markdown: bool = True,
    ) -> TranscriptResult:
        lang = (languages[0] if languages else "en") or "en"
        # map common codes
        if lang.startswith("en"):
            lang = "en"
        ocr = _get_ocr(lang)
        if ocr is None:
            return TranscriptResult(
                text="",
                engine=self.name,
                error="PaddleOCR not installed or failed to load",
            )
        try:
            prepared = prepare_for_ocr(image, for_vision=False)
            arr = np.array(prepared)
            # paddleocr API: ocr(img) or predict
            try:
                result = ocr.ocr(arr, cls=True)
            except TypeError:
                result = ocr.ocr(arr)

            lines: list[str] = []
            scores: list[float] = []
            # result often: [ [ [box, (text, score)], ... ] ]
            pages = result if result else []
            for page in pages:
                if not page:
                    continue
                for row in page:
                    if not row or len(row) < 2:
                        continue
                    info = row[1]
                    if isinstance(info, (list, tuple)) and len(info) >= 1:
                        lines.append(str(info[0]))
                        if len(info) > 1 and isinstance(info[1], (int, float)):
                            scores.append(float(info[1]))
                    else:
                        lines.append(str(info))
            text = clean_ocr_output("\n".join(lines))
            conf = sum(scores) / len(scores) if scores else None
            return TranscriptResult(text=text, engine=self.name, confidence=conf, format="plain")
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
