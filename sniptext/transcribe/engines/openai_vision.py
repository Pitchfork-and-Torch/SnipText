"""OpenAI vision transcription."""

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
from sniptext.transcribe.postprocess import clean_vision_output, maybe_plain
from sniptext.transcribe.preprocess import prepare_for_ocr, to_png_bytes


class OpenAIVisionTranscriber:
    name = "openai_vision"

    def __init__(
        self,
        model: str = "gpt-4o",
        detail: str = "high",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self.detail = detail
        self._api_key = api_key

    def _key(self) -> Optional[str]:
        return self._api_key or get_secret("openai_api_key")

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
            return TranscriptResult(text="", engine=self.name, error="No OpenAI API key")
        try:
            from openai import OpenAI
        except ImportError:
            return TranscriptResult(text="", engine=self.name, error="openai package not installed")

        prepared = prepare_for_ocr(image, for_vision=True)
        b64 = base64.b64encode(to_png_bytes(prepared)).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"

        try:
            client = OpenAI(api_key=key)
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
            text = clean_vision_output(resp.choices[0].message.content or "")
            text = maybe_plain(text, prefer_markdown)
            return TranscriptResult(
                text=text,
                engine=self.name,
                format="markdown" if prefer_markdown else "plain",
            )
        except Exception as exc:
            return TranscriptResult(text="", engine=self.name, error=str(exc))
