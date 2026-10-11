"""Anthropic Claude vision transcription."""

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


class AnthropicVisionTranscriber:
    name = "anthropic_vision"

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self._api_key = api_key

    def _key(self) -> Optional[str]:
        return self._api_key or get_secret("anthropic_api_key")

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
            return TranscriptResult(text="", engine=self.name, error="No Anthropic API key")

        prepared = prepare_for_ocr(image, for_vision=True)
        b64 = base64.b64encode(to_png_bytes(prepared)).decode("ascii")

        payload = {
            "model": self.model,
            "max_tokens": 8192,
            "system": VISION_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": VISION_USER_PROMPT},
                    ],
                }
            ],
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
            parts = data.get("content") or []
            raw = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
            text = maybe_plain(clean_vision_output(raw), prefer_markdown)
            return TranscriptResult(
                text=text,
                engine=self.name,
                format="markdown" if prefer_markdown else "plain",
            )
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
