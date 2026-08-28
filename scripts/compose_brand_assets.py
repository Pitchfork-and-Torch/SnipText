"""Compose logo variants, OG tweet card, and landscape infographic with exact text."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(os.environ["USERPROFILE"]) / "SnipText"
BRAND = ROOT / "brand"
LAND = ROOT / "landing" / "public"
ASSETS = ROOT / "assets"
DESK = Path(os.environ["USERPROFILE"]) / "Desktop" / "SnipText-tweet-ready"
SESSION_IMAGES = (
    Path(os.environ["USERPROFILE"])
    / ".grok"
    / "sessions"
    / "C%3A%5CUsers%5CKnock"
    / "019fd941-c66f-79b1-90d4-ba8f360fa568"
    / "images"
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    cands = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in cands:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    bw, bh = img.size
    scale = max(w / bw, h / bh)
    nw, nh = int(bw * scale), int(bh * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def main() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    (LAND / "assets").mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    DESK.mkdir(parents=True, exist_ok=True)

    # Prefer session images if brand sources missing
    src_logo = BRAND / "logo-source.jpg"
    src_hero = BRAND / "hero-bg-source.jpg"
    src_steps = BRAND / "steps-bg-source.jpg"
    if not src_logo.is_file() and (SESSION_IMAGES / "1.jpg").is_file():
        Image.open(SESSION_IMAGES / "1.jpg").save(src_logo, quality=95)
    if not src_hero.is_file() and (SESSION_IMAGES / "2.jpg").is_file():
        Image.open(SESSION_IMAGES / "2.jpg").save(src_hero, quality=95)
    if not src_steps.is_file() and (SESSION_IMAGES / "3.jpg").is_file():
        Image.open(SESSION_IMAGES / "3.jpg").save(src_steps, quality=95)

    # Logo
    logo = Image.open(src_logo).convert("RGBA")
    s = min(logo.size)
    logo = logo.crop(
        ((logo.width - s) // 2, (logo.height - s) // 2, (logo.width + s) // 2, (logo.height + s) // 2)
    )
    logo_512 = logo.resize((512, 512), Image.Resampling.LANCZOS)
    logo_512.save(BRAND / "logo-512.png")
    logo_512.save(ASSETS / "icon.png")
    logo_512.resize((192, 192), Image.Resampling.LANCZOS).save(LAND / "icon-192.png")
    logo_512.resize((512, 512), Image.Resampling.LANCZOS).save(LAND / "icon-512.png")
    icos = [logo_512.resize((n, n), Image.Resampling.LANCZOS) for n in (16, 32, 48, 64, 128, 256)]
    icos[-1].save(ASSETS / "icon.ico", format="ICO", sizes=[(n, n) for n in (16, 32, 48, 64, 128, 256)])
    icos[-1].save(LAND / "favicon.ico", format="ICO", sizes=[(n, n) for n in (16, 32, 48, 64)])
    print("logo ok")

    # OG 1200x630
    W, H = 1200, 630
    bg = cover_crop(Image.open(src_hero).convert("RGB"), W, H).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dov = ImageDraw.Draw(overlay)
    for y in range(H):
        a = int(140 + 70 * (y / H))
        dov.line([(0, y), (W, y)], fill=(8, 12, 24, min(210, a)))
    dov.rectangle([0, 0, 740, H], fill=(8, 12, 24, 120))
    card = Image.alpha_composite(bg, overlay)
    badge = logo_512.resize((120, 120), Image.Resampling.LANCZOS)
    card.paste(badge, (72, 90), badge)
    draw = ImageDraw.Draw(card)
    draw.text((220, 100), "SnipText", font=font(64, True), fill=(248, 250, 252, 255))
    draw.text((220, 178), "1.2 The Ledger  ·  Snip. Read. Clipboard.", font=font(22), fill=(91, 219, 255, 255))
    draw.text((72, 280), "Click. Drag. Transcribe.", font=font(42, True), fill=(241, 245, 249, 255))
    draw.text((72, 340), "Accurate text from any on-screen region,", font=font(24), fill=(203, 213, 225, 255))
    draw.text((72, 376), "copied to your clipboard in one fluid motion.", font=font(24), fill=(203, 213, 225, 255))
    chips = [("1  Click", 72), ("2  Drag", 250), ("3  Paste", 430)]
    for label, x in chips:
        draw.rounded_rectangle(
            [x, 460, x + 150, 520],
            radius=18,
            fill=(15, 23, 42, 220),
            outline=(91, 219, 255, 180),
            width=2,
        )
        draw.text((x + 22, 476), label, font=font(22, True), fill=(226, 232, 240, 255))
    draw.text((72, 560), "by Pitchfork-and-Torch", font=font(18), fill=(148, 163, 184, 255))
    og = card.convert("RGB")
    for path in (
        LAND / "og.jpg",
        LAND / "share-card.jpg",
        BRAND / "tweet-card-1200x630.jpg",
        DESK / "tweet-card-1200x630.jpg",
    ):
        og.save(path, quality=92, optimize=True)
    og.save(LAND / "og.png", optimize=True)
    print("og ok")

    # Infographic 1600x900
    IW, IH = 1600, 900
    base = cover_crop(Image.open(src_steps).convert("RGB"), IW, IH).convert("RGBA")
    veil = Image.new("RGBA", (IW, IH), (6, 10, 20, 160))
    inf = Image.alpha_composite(base, veil)
    d = ImageDraw.Draw(inf)
    mark = logo_512.resize((88, 88), Image.Resampling.LANCZOS)
    inf.paste(mark, (72, 48), mark)
    d.text((180, 55), "SnipText", font=font(48, True), fill=(248, 250, 252, 255))
    d.text((180, 112), "The premium way to grab on-screen text", font=font(24), fill=(148, 163, 184, 255))
    cards_info = [
        (80, "Click", "Press the hotkey.\nA calm dim overlay\ncovers every display."),
        (580, "Drag", "Draw a region like the\nSnipping Tool - live\nsize, Escape cancels."),
        (1080, "Paste", "Accurate text lands on\nyour clipboard. Edit,\ncopy again, or re-run."),
    ]
    for x, title, body in cards_info:
        d.rounded_rectangle(
            [x, 220, x + 440, 720],
            radius=28,
            fill=(15, 23, 42, 210),
            outline=(91, 219, 255, 100),
            width=2,
        )
        d.text((x + 36, 260), title, font=font(40, True), fill=(91, 219, 255, 255))
        yy = 340
        for line in body.split("\n"):
            d.text((x + 36, yy), line, font=font(24), fill=(226, 232, 240, 255))
            yy += 40
    d.text(
        (80, 780),
        "Vision AI when you add a key  ·  Local OCR offline  ·  Privacy-first",
        font=font(22),
        fill=(148, 163, 184, 255),
    )
    d.text(
        (80, 830),
        "MIT License  ·  Credit Pitchfork-and-Torch when you reuse  ·  sniptext.jonbailey.xyz",
        font=font(18),
        fill=(100, 116, 139, 255),
    )
    inf_rgb = inf.convert("RGB")
    inf_rgb.save(BRAND / "infographic-landscape.jpg", quality=93)
    inf_rgb.save(LAND / "assets" / "infographic.jpg", quality=93)
    inf_rgb.save(DESK / "infographic-landscape.jpg", quality=93)
    print("infographic ok")

    hero = Image.open(src_hero).convert("RGB")
    hero = cover_crop(hero, 1920, 1080)
    hero = ImageEnhance.Brightness(hero).enhance(0.72)
    hero.save(LAND / "assets" / "hero.jpg", quality=90)
    print("hero ok")
    print("ALL BRAND OK")


if __name__ == "__main__":
    main()
