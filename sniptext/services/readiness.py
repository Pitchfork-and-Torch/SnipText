"""Local OCR / vision readiness checks for first-run and About."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class EngineStatus:
    name: str
    ready: bool
    detail: str


def check_local_engines() -> List[EngineStatus]:
    out: list[EngineStatus] = []

    # RapidOCR
    try:
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401
        except ImportError:
            from rapidocr import RapidOCR  # type: ignore  # noqa: F401
        out.append(EngineStatus("RapidOCR", True, "Installed - good default local OCR"))
    except Exception as exc:
        out.append(
            EngineStatus(
                "RapidOCR",
                False,
                f"Not available ({exc}). pip install rapidocr-onnxruntime",
            )
        )

    # Paddle
    try:
        import paddleocr  # noqa: F401

        out.append(EngineStatus("PaddleOCR", True, "Installed"))
    except Exception:
        out.append(EngineStatus("PaddleOCR", False, "Optional - not installed"))

    # EasyOCR
    try:
        import easyocr  # noqa: F401

        out.append(EngineStatus("EasyOCR", True, "Installed"))
    except Exception:
        out.append(EngineStatus("EasyOCR", False, "Optional - not installed"))

    # Tesseract
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        out.append(EngineStatus("Tesseract", True, "System binary found"))
    except Exception:
        out.append(EngineStatus("Tesseract", False, "Optional - not installed"))

    return out


def any_local_ready() -> bool:
    return any(s.ready for s in check_local_engines())


def readiness_summary() -> str:
    statuses = check_local_engines()
    ready = [s.name for s in statuses if s.ready]
    if ready:
        return f"Local OCR ready: {', '.join(ready)}"
    return (
        "Local OCR not found. Connect an AI key for transcription, "
        "or install rapidocr-onnxruntime for offline use."
    )


def full_status_report() -> str:
    lines = [readiness_summary(), ""]
    for s in check_local_engines():
        mark = "OK" if s.ready else "--"
        lines.append(f"  [{mark}] {s.name}: {s.detail}")
    return "\n".join(lines)
