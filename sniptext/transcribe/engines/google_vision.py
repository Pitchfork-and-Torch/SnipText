"""Google Gemini vision transcription (generativelanguage API)."""

from __future__ import annotations

import base64
from typing import Optional

import httpx
from PIL import Image

from sniptext.services.secrets import get_secret
from sniptext.transcribe.base import (
    VISION_SYSTEM_PROMPT,
    VISION_USER_PROMPT,
    TranscriptResult,
)
from sniptext.transcribe.postprocess import clean_vision_output, maybe_plain
from sniptext.transcribe.preprocess import prepare_for_ocr, to_png_bytes


class GoogleVisionTranscriber:
    name = "google_vision"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self._api_key = api_key

    def _key(self) -> Optional[str]:
        return self._api_key or get_secret("google_api_key")

    def available(self) -> bool:
        return bool(self._key())

    def transcribe(
        self,
        image: Image.Image,
        *,
        languages: list[str],
        prefer_markdown: bool = True,
    ) -> TranscriptResult:
        key = self._key()
        if not key:
            return TranscriptResult(text="", engine=self.name, error="No Google API key")

        prepared = prepare_for_ocr(image, for_vision=True)
        b64 = base64.b64encode(to_png_bytes(prepared)).decode("ascii")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": VISION_SYSTEM_PROMPT}]},
            "contents": [
                {
                    "parts": [
                        {"text": VISION_USER_PROMPT},
                        {"inline_data": {"mime_type": "image/png", "data": b64}},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 8192},
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
            cands = data.get("candidates") or []
            raw = ""
            if cands:
                parts = cands[0].get("content", {}).get("parts") or []
                raw = "".join(p.get("text", "") for p in parts)
            text = maybe_plain(clean_vision_output(raw), prefer_markdown)
            return TranscriptResult(
                text=text,
                engine=self.name,
                format="markdown" if prefer_markdown else "plain",
            )
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
