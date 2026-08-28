"""Route images to vision / local OCR engines by priority."""

from __future__ import annotations

import logging
from typing import Any, Optional

from PIL import Image

from sniptext.services.secrets import has_any_vision_key
from sniptext.transcribe.base import TranscriptResult
from sniptext.transcribe.engines.anthropic_vision import AnthropicVisionTranscriber
from sniptext.transcribe.engines.easy_ocr import EasyOCRTranscriber
from sniptext.transcribe.engines.google_vision import GoogleVisionTranscriber
from sniptext.transcribe.engines.openai_vision import OpenAIVisionTranscriber
from sniptext.transcribe.engines.paddle_ocr import PaddleOCRTranscriber
from sniptext.transcribe.engines.rapid_ocr import RapidOCRTranscriber
from sniptext.transcribe.engines.tesseract_ocr import TesseractTranscriber
from sniptext.transcribe.engines.xai_vision import XAIVisionTranscriber

log = logging.getLogger("sniptext.router")


class EngineRouter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        model = config.get("vision_model") or "grok-4.5"
        detail = config.get("vision_detail") or "high"
        self._vision = [
            XAIVisionTranscriber(model=model, detail=detail),
            OpenAIVisionTranscriber(detail=detail),
            AnthropicVisionTranscriber(),
            GoogleVisionTranscriber(),
        ]
        order = config.get("local_engine_order") or [
            "paddle",
            "rapid",
            "easyocr",
            "tesseract",
        ]
        local_map = {
            "paddle": PaddleOCRTranscriber(),
            "rapid": RapidOCRTranscriber(),
            "easyocr": EasyOCRTranscriber(),
            "tesseract": TesseractTranscriber(),
        }
        self._local = [local_map[n] for n in order if n in local_map]
        # ensure all known engines present even if order incomplete
        for name, eng in local_map.items():
            if eng not in self._local:
                self._local.append(eng)

    def update_config(self, config: dict[str, Any]) -> None:
        self.__init__(config)

    def list_available(self) -> dict[str, list[str]]:
        return {
            "vision": [e.name for e in self._vision if e.available()],
            "local": [e.name for e in self._local if e.available()],
        }

    def transcribe(self, image: Image.Image) -> TranscriptResult:
        mode = (self.config.get("engine_mode") or "ai_first").lower()
        languages = list(self.config.get("languages") or ["en"])
        prefer_md = (self.config.get("output_format") or "markdown") == "markdown"

        if mode == "local_only":
            return self._run_local(image, languages, prefer_md)

        if mode == "ai_only":
            result = self._run_vision(image, languages, prefer_md)
            if result.ok:
                return result
            return TranscriptResult(
                text="",
                engine=result.engine if result else "vision",
                error=result.error or "AI transcription failed (ai_only mode, no local fallback)",
            )

        # ai_first
        if has_any_vision_key():
            result = self._run_vision(image, languages, prefer_md)
            if result.ok:
                return result
            log.warning("Vision failed (%s); falling back to local", result.error)
        return self._run_local(image, languages, prefer_md)

    def transcribe_local_only(self, image: Image.Image) -> TranscriptResult:
        languages = list(self.config.get("languages") or ["en"])
        prefer_md = (self.config.get("output_format") or "markdown") == "markdown"
        return self._run_local(image, languages, prefer_md)

    def _run_vision(
        self,
        image: Image.Image,
        languages: list[str],
        prefer_md: bool,
    ) -> TranscriptResult:
        last = TranscriptResult(text="", engine="vision", error="No vision engine available")
        for eng in self._vision:
            if not eng.available():
                continue
            last = eng.transcribe(image, languages=languages, prefer_markdown=prefer_md)
            if last.ok:
                return last
            log.info("Engine %s failed: %s", eng.name, last.error)
        return last

    def _run_local(
        self,
        image: Image.Image,
        languages: list[str],
        prefer_md: bool,
    ) -> TranscriptResult:
        last = TranscriptResult(
            text="",
            engine="local",
            error=(
                "No local OCR engine available. Install one of: "
                "rapidocr-onnxruntime, paddleocr, easyocr, or tesseract+pytesseract"
            ),
        )
        for eng in self._local:
            if not eng.available():
                continue
            last = eng.transcribe(image, languages=languages, prefer_markdown=prefer_md)
            if last.ok:
                return last
            if last.error:
                log.info("Engine %s: %s", eng.name, last.error)
        if not last.ok and not last.error:
            last.error = "No text detected"
        return last
