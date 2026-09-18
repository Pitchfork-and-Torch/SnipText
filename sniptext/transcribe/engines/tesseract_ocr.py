"""Tesseract local engine (system binary + pytesseract)."""

from __future__ import annotations

from PIL import Image

from sniptext.transcribe.base import TranscriptResult
from sniptext.transcribe.postprocess import clean_ocr_output
from sniptext.transcribe.preprocess import prepare_for_ocr


class TesseractTranscriber:
    name = "tesseract"

    def available(self) -> bool:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def transcribe(
        self,
        image: Image.Image,
        *,
        languages: list[str],
        prefer_markdown: bool = True,
    ) -> TranscriptResult:
        try:
            import pytesseract
        except ImportError:
            return TranscriptResult(
                text="",
                engine=self.name,
                error="pytesseract not installed",
            )
        try:
            prepared = prepare_for_ocr(image, for_vision=False)
            lang = "+".join(languages) if languages else "eng"
            # map en -> eng
            lang = lang.replace("en", "eng") if lang in ("en", "en+eng") else lang
            if lang == "en":
                lang = "eng"
            text = pytesseract.image_to_string(prepared, lang=lang)
            return TranscriptResult(
                text=clean_ocr_output(text),
                engine=self.name,
                format="plain",
            )
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
