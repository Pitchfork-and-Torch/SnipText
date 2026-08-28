"""Vision provider metadata, links, and connection tests for easy API setup."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    secret_name: str
    label: str
    short: str
    get_key_url: str
    help_blurb: str
    default_model: str
    recommended: bool = False


PROVIDERS: tuple[ProviderInfo, ...] = (
    ProviderInfo(
        id="xai",
        secret_name="xai_api_key",
        label="xAI (Grok) - recommended",
        short="xAI",
        get_key_url="https://console.x.ai/",
        help_blurb="Best accuracy for screenshots and code. Create a key at console.x.ai, paste it below, then Test.",
        default_model="grok-4.5",
        recommended=True,
    ),
    ProviderInfo(
        id="openai",
        secret_name="openai_api_key",
        label="OpenAI",
        short="OpenAI",
        get_key_url="https://platform.openai.com/api-keys",
        help_blurb="Uses GPT vision models. Create a key at platform.openai.com, paste, then Test.",
        default_model="gpt-4o",
    ),
    ProviderInfo(
        id="anthropic",
        secret_name="anthropic_api_key",
        label="Anthropic (Claude)",
        short="Anthropic",
        get_key_url="https://console.anthropic.com/settings/keys",
        help_blurb="Uses Claude vision. Create a key in the Anthropic console, paste, then Test.",
        default_model="claude-sonnet-4-20250514",
    ),
    ProviderInfo(
        id="google",
        secret_name="google_api_key",
        label="Google (Gemini)",
        short="Google",
        get_key_url="https://aistudio.google.com/apikey",
        help_blurb="Uses Gemini vision. Create an API key in Google AI Studio, paste, then Test.",
        default_model="gemini-2.0-flash",
    ),
)

PROVIDER_BY_ID = {p.id: p for p in PROVIDERS}
PROVIDER_BY_SECRET = {p.secret_name: p for p in PROVIDERS}

ENGINE_MODE_CHOICES = (
    ("ai_first", "AI when available (recommended)"),
    ("local_only", "Local OCR only (never network)"),
    ("ai_only", "AI only (no local fallback)"),
)

ENGINE_MODE_LABELS = {k: v for k, v in ENGINE_MODE_CHOICES}
ENGINE_MODE_FROM_LABEL = {v: k for k, v in ENGINE_MODE_CHOICES}


def provider_status_line() -> str:
    """Human status for tray/settings: which keys are connected."""
    from sniptext.services import secrets

    connected = [p.short for p in PROVIDERS if secrets.get_secret(p.secret_name)]
    if not connected:
        return "Local OCR only - add an AI key for max accuracy"
    if len(connected) == 1:
        return f"AI connected: {connected[0]}"
    return "AI connected: " + ", ".join(connected)


def connected_provider_ids() -> list[str]:
    from sniptext.services import secrets

    return [p.id for p in PROVIDERS if secrets.get_secret(p.secret_name)]


def _tiny_test_image() -> Image.Image:
    img = Image.new("RGB", (160, 48), "white")
    d = ImageDraw.Draw(img)
    d.text((8, 14), "OK 42", fill="black")
    return img


def test_provider_connection(
    provider_id: str,
    api_key: str,
    *,
    model: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Quick live check that a key works for vision.
    Returns (ok, message). Never logs the key.
    """
    key = (api_key or "").strip()
    if not key:
        return False, "Paste an API key first."
    if key.startswith("*") and len(key) < 20:
        return False, "Enter the full key (not the masked placeholder)."

    info = PROVIDER_BY_ID.get(provider_id)
    if not info:
        return False, f"Unknown provider: {provider_id}"

    model = (model or info.default_model).strip()
    img = _tiny_test_image()

    try:
        if provider_id == "xai":
            return _test_openai_compatible(
                key,
                base_url="https://api.x.ai/v1",
                model=model,
                label="xAI",
                image=img,
            )
        if provider_id == "openai":
            return _test_openai_compatible(
                key,
                base_url=None,
                model=model,
                label="OpenAI",
                image=img,
            )
        if provider_id == "anthropic":
            return _test_anthropic(key, model=model, image=img)
        if provider_id == "google":
            return _test_google(key, model=model, image=img)
    except Exception as exc:
        return False, _friendly_error(str(exc))

    return False, "Unsupported provider."


def _png_b64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _test_openai_compatible(
    key: str,
    *,
    base_url: Optional[str],
    model: str,
    label: str,
    image: Image.Image,
) -> tuple[bool, str]:
    try:
        from openai import OpenAI
    except ImportError:
        return False, "openai package missing from this install."

    kwargs = {"api_key": key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    data_url = f"data:image/png;base64,{_png_b64(image)}"
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=32,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "low"},
                        },
                        {
                            "type": "text",
                            "text": "Reply with only the text you see in the image.",
                        },
                    ],
                }
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return False, f"{label} responded empty. Check model id ({model})."
        return True, f"Connected to {label}. Vision works (model {model})."
    except Exception as exc:
        return False, _friendly_error(str(exc), label=label)


def _test_anthropic(key: str, *, model: str, image: Image.Image) -> tuple[bool, str]:
    import httpx

    payload = {
        "model": model,
        "max_tokens": 32,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": _png_b64(image),
                        },
                    },
                    {
                        "type": "text",
                        "text": "Reply with only the text you see in the image.",
                    },
                ],
            }
        ],
    }
    try:
        with httpx.Client(timeout=45.0) as client:
            r = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            if r.status_code >= 400:
                return False, _friendly_error(r.text[:240], label="Anthropic")
            data = r.json()
        parts = data.get("content") or []
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        if not text.strip():
            return False, "Anthropic responded empty. Check model id."
        return True, f"Connected to Anthropic. Vision works (model {model})."
    except Exception as exc:
        return False, _friendly_error(str(exc), label="Anthropic")


def _test_google(key: str, *, model: str, image: Image.Image) -> tuple[bool, str]:
    import httpx

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Reply with only the text you see in the image."},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": _png_b64(image),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 32},
    }
    try:
        with httpx.Client(timeout=45.0) as client:
            r = client.post(url, json=payload)
            if r.status_code >= 400:
                return False, _friendly_error(r.text[:240], label="Google")
            data = r.json()
        cands = data.get("candidates") or []
        raw = ""
        if cands:
            parts = cands[0].get("content", {}).get("parts") or []
            raw = "".join(p.get("text", "") for p in parts)
        if not raw.strip():
            return False, "Google responded empty. Check model id."
        return True, f"Connected to Google. Vision works (model {model})."
    except Exception as exc:
        return False, _friendly_error(str(exc), label="Google")


def _friendly_error(raw: str, label: str = "API") -> str:
    low = (raw or "").lower()
    if "401" in low or "unauthorized" in low or "invalid api key" in low or "incorrect api key" in low:
        return f"{label}: invalid API key. Double-check you pasted the full key."
    if "429" in low or "rate" in low:
        return f"{label}: rate limited. Wait a moment and try again."
    if "model" in low and ("not found" in low or "does not exist" in low):
        return f"{label}: model not found. Try the default model for this provider."
    if "connection" in low or "timeout" in low or "network" in low:
        return f"{label}: network error. Check internet / VPN / firewall."
    # Truncate technical noise
    msg = " ".join((raw or "Unknown error").split())
    if len(msg) > 180:
        msg = msg[:177] + "..."
    return f"{label}: {msg}"
