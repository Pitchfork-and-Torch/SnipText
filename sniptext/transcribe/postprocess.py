"""Post-process transcription text."""

from __future__ import annotations

import re


_PREAMBLE_RE = re.compile(
    r"^(here(?:'s| is) (?:the )?(?:transcri(?:bed|ption)|text|extracted text)[:\s]*)",
    re.IGNORECASE,
)


def clean_vision_output(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    # Strip accidental whole-answer fences
    if t.startswith("```") and t.endswith("```"):
        lines = t.splitlines()
        if len(lines) >= 2:
            # drop first fence line and last
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            t = "\n".join(lines).strip()
    t = _PREAMBLE_RE.sub("", t).strip()
    if t.lower() in ("[no text detected]", "no text detected", "(no text detected)"):
        return ""
    return t


def clean_ocr_output(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ blank lines
    t = re.sub(r"\n{3,}", "\n\n", t)
    # Strip trailing spaces per line, keep indent leading
    lines = [re.sub(r"[ \t]+$", "", line) for line in t.split("\n")]
    t = "\n".join(lines).strip()
    return t


def maybe_plain(text: str, prefer_markdown: bool) -> str:
    if prefer_markdown:
        return text
    # crude strip of md emphasis for plain mode
    t = re.sub(r"[*_`]+", "", text)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    return t
