"""Transcriber protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from PIL import Image


@dataclass
class TranscriptResult:
    text: str
    engine: str
    confidence: Optional[float] = None
    format: str = "markdown"
    raw: Optional[dict[str, Any]] = field(default=None, repr=False)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return bool((self.text or "").strip()) and not self.error


@runtime_checkable
class Transcriber(Protocol):
    name: str

    def available(self) -> bool: ...

    def transcribe(
        self,
        image: Image.Image,
        *,
        languages: list[str],
        prefer_markdown: bool = True,
    ) -> TranscriptResult: ...


VISION_SYSTEM_PROMPT = """You are an expert OCR and document transcription engine.
Extract ALL text from the provided screenshot with maximum accuracy.

Rules:
- Output ONLY the transcribed content. No preamble, no commentary, no markdown fences around the whole answer unless the content itself is code.
- Preserve structure using Markdown where helpful:
  - Tables -> GitHub-flavored Markdown tables
  - Code / terminal / editors -> fenced code blocks with original indentation and whitespace
  - Lists, headings, and paragraphs as they appear
- Handle UI chrome labels, low-contrast text, multi-language content, handwriting, and math (prefer LaTeX for equations).
- Do not invent text that is not visible. If no text is present, output exactly: [No text detected]
"""

VISION_USER_PROMPT = (
    "Transcribe every readable character in this image. "
    "Preserve layout and code indentation. Output only the transcription."
)
