"""RapidOCR (ONNX) local engine - lightweight default on modern Python."""

from __future__ import annotations

from typing import Any, Optional

from PIL import Image
import numpy as np

from sniptext.transcribe.base import TranscriptResult
from sniptext.transcribe.postprocess import clean_ocr_output
from sniptext.transcribe.preprocess import prepare_for_ocr

_engine: Any = None
_failed = False


def _get_engine() -> Any:
    global _engine, _failed
    if _failed:
        return None
    if _engine is not None:
        return _engine
    try:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            from rapidocr import RapidOCR  # type: ignore

        _engine = RapidOCR()
        return _engine
    except Exception:
        _failed = True
        return None


class RapidOCRTranscriber:
    name = "rapid"

    def available(self) -> bool:
        return _get_engine() is not None

    def transcribe(
        self,
        image: Image.Image,
        *,
        languages: list[str],
        prefer_markdown: bool = True,
    ) -> TranscriptResult:
        eng = _get_engine()
        if eng is None:
            return TranscriptResult(
                text="",
                engine=self.name,
                error="RapidOCR not installed (pip install rapidocr-onnxruntime)",
            )
        try:
            prepared = prepare_for_ocr(image, for_vision=False)
            arr = np.array(prepared)
            result, _elapsed = eng(arr)
            if not result:
                return TranscriptResult(text="", engine=self.name)
            # result: list of [box, text, score]
            lines: list[str] = []
            scores: list[float] = []
            for item in result:
                if not item or len(item) < 2:
                    continue
                text = item[1] if not isinstance(item[1], (list, tuple)) else str(item[1])
                # rapidocr formats vary slightly by version
                if isinstance(item, (list, tuple)):
                    if len(item) >= 3 and isinstance(item[2], (int, float)):
                        scores.append(float(item[2]))
                    # Sometimes [box, (text, score)]
                    if isinstance(item[1], (list, tuple)) and len(item[1]) >= 1:
                        text = str(item[1][0])
                        if len(item[1]) > 1 and isinstance(item[1][1], (int, float)):
                            scores.append(float(item[1][1]))
                lines.append(str(text))
            joined = clean_ocr_output("\n".join(lines))
            conf = sum(scores) / len(scores) if scores else None
            return TranscriptResult(text=joined, engine=self.name, confidence=conf, format="plain")
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
