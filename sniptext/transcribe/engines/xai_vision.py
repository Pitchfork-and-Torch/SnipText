"""xAI Grok vision transcription (OpenAI-compatible API)."""

from __future__ import annotations

import base64
from typing import Optional

from PIL import Image

from sniptext.services.secrets import get_secret
from sniptext.transcribe.base import (
    VISION_SYSTEM_PROMPT,
    VISION_USER_PROMPT,
    TranscriptResult,
)
from sniptext.transcribe.postprocess import clean_vision_output
from sniptext.transcribe.preprocess import prepare_for_ocr, to_png_bytes


class XAIVisionTranscriber:
    name = "xai_vision"

    def __init__(
        self,
        model: str = "grok-4.5",
        detail: str = "high",
        api_key: Optional[str] = None,
        base_url: str = "https://api.x.ai/v1",
    ) -> None:
        self.model = model
        self.detail = detail
        self._api_key = api_key
        self.base_url = base_url

    def _key(self) -> Optional[str]:
        return self._api_key or get_secret("xai_api_key")

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
            return TranscriptResult(text="", engine=self.name, error="No xAI API key")

        try:
            from openai import OpenAI
        except ImportError:
            return TranscriptResult(text="", engine=self.name, error="openai package not installed")

        prepared = prepare_for_ocr(image, for_vision=True)
        b64 = base64.b64encode(to_png_bytes(prepared)).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"

        try:
            client = OpenAI(api_key=key, base_url=self.base_url)
            # Chat Completions with image_url - widely supported on xAI
            resp = client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_tokens=8192,
                messages=[
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url, "detail": self.detail},
                            },
                            {"type": "text", "text": VISION_USER_PROMPT},
                        ],
                    },
                ],
            )
            raw = (resp.choices[0].message.content or "").strip()
            text = clean_vision_output(raw)
            if not prefer_markdown:
                from sniptext.transcribe.postprocess import maybe_plain

                text = maybe_plain(text, prefer_markdown=False)
            return TranscriptResult(text=text, engine=self.name, format="markdown" if prefer_markdown else "plain")
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
