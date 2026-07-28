#!/usr/bin/env python3
"""Generate icon/logo assets for RoomFlow.

Produces the files required by the home-assistant/brands repo
(icon.png, icon@2x.png, logo.png, logo@2x.png) plus a copy of the
icon at repo root for use in the README.

Usage: python3 scripts/generate_logo.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "brands" / "custom_integrations" / "roomflow"
BRAND_DIR.mkdir(parents=True, exist_ok=True)

HOUSE_COLOR = (3, 155, 229, 255)   # room/home
BOLT_COLOR = (255, 179, 0, 255)    # flow/power
TEXT_COLOR = (33, 33, 33, 255)

SUPERSAMPLE = 4


def draw_icon(size: int) -> Image.Image:
    """Draw a simple house silhouette with a lightning bolt cut through it,
    echoing the sidebar panel's mdi:home-lightning-bolt-outline icon."""
    big = size * SUPERSAMPLE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = big / 2
    roof_apex_y = big * 0.10
    roof_base_y = big * 0.42
    wall_left = big * 0.16
    wall_right = big * 0.84
    wall_bottom = big * 0.86

    # Roof (triangle)
    draw.polygon(
        [(cx, roof_apex_y), (wall_right, roof_base_y), (wall_left, roof_base_y)],
        fill=HOUSE_COLOR,
    )
    # Walls (only the bottom corners rounded, so the top edge aligns exactly
    # with the roof triangle's base with no seam)
    draw.rounded_rectangle(
        [wall_left, roof_base_y - big * 0.02, wall_right, wall_bottom],
        radius=big * 0.05,
        corners=(False, False, True, True),
        fill=HOUSE_COLOR,
    )

    # Lightning bolt, cut through the house's center
    bw, bh = big * 0.26, big * 0.52
    bx, by = cx - bw / 2, roof_base_y + big * 0.06
    norm = [
        (0.60, 0.0), (0.0, 0.55), (0.35, 0.55),
        (0.25, 1.0), (1.0, 0.40), (0.55, 0.40),
    ]
    bolt = [(bx + nx * bw, by + ny * bh) for nx, ny in norm]
    draw.polygon(bolt, fill=BOLT_COLOR)

    return img.resize((size, size), Image.LANCZOS)


def draw_logo(icon_size: int) -> Image.Image:
    """Icon + wordmark, transparent background, height == icon_size."""
    icon = draw_icon(icon_size)
    font_size = int(icon_size * 0.46)
    font = ImageFont.truetype(
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size
    )

    text = "RoomFlow"
    measure = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    bbox = measure.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    gap = int(icon_size * 0.18)
    width = icon_size + gap + text_w + int(icon_size * 0.08)
    logo = Image.new("RGBA", (width, icon_size), (0, 0, 0, 0))
    logo.paste(icon, (0, 0), icon)

    draw = ImageDraw.Draw(logo)
    text_y = (icon_size - text_h) / 2 - bbox[1]
    draw.text((icon_size + gap, text_y), text, font=font, fill=TEXT_COLOR)
    return logo


def main():
    draw_icon(256).save(BRAND_DIR / "icon.png")
    draw_icon(512).save(BRAND_DIR / "icon@2x.png")
    draw_logo(256).save(BRAND_DIR / "logo.png")
    draw_logo(512).save(BRAND_DIR / "logo@2x.png")

    # Convenience copies for the repo's own README / GitHub social preview.
    draw_icon(512).save(ROOT / "icon.png")
    draw_logo(512).save(ROOT / "logo.png")

    print(f"Wrote assets to {BRAND_DIR} and repo root")


if __name__ == "__main__":
    main()
