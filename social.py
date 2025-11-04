"""Social asset generation for Instagram and TikTok."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from models import DealSummary
from utils import normalize_whitespace

INSTAGRAM_MAX_HASHTAGS = 30
TIKTOK_NOTES = "Exported captions/images should be uploaded via TikTok's Content Posting API."
DEFAULT_HASHTAGS = "#AmazonDeals #CanadaDeals #DealsCanada #OnSale #YULDeals"


try:
    DEFAULT_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
    SMALL_FONT = ImageFont.truetype("DejaVuSans.ttf", 36)
except OSError:  # pragma: no cover
    DEFAULT_FONT = ImageFont.load_default()
    SMALL_FONT = ImageFont.load_default()


def generate_caption(deal: DealSummary) -> Tuple[str, str]:
    """Create a concise, emoji-driven caption and hashtag string."""

    product_name = deal.get("product_name") or "Amazon.ca Deal"
    deal_price = deal.get("deal_price")
    savings_percent = deal.get("savings_percent")
    if deal_price is not None:
        price_str = f"${deal_price:,.2f}"
    else:
        price_str = "on sale"
    savings_text = ""
    if savings_percent:
        savings_text = f" (save {savings_percent:.0f}%)"
    caption = f"🔥 DEAL ALERT: {product_name} now {price_str}{savings_text}! Link in bio."
    if len(caption) > 150:
        caption = caption[:147] + "..."
    return caption, DEFAULT_HASHTAGS


def render_card_image(deal: DealSummary, out_path: Path) -> Path:
    """Render a simple 1080x1080 PNG card summarising the deal."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    product_name = normalize_whitespace(deal.get("product_name") or "Amazon.ca Deal")
    price = deal.get("deal_price")
    price_text = f"${price:,.2f}" if price is not None else "Limited Offer"
    canvas = Image.new("RGB", (1080, 1080), color=(245, 245, 245))
    draw = ImageDraw.Draw(canvas)

    draw.rectangle([(0, 0), (1080, 200)], fill=(33, 33, 33))
    draw.text((40, 70), "Amazon.ca Deal", font=SMALL_FONT, fill=(255, 255, 255))

    text_box_width = 1000
    y_offset = 260
    words = product_name.split()
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        w, _ = draw.textsize(test_line, font=DEFAULT_FONT)
        if w > text_box_width and current_line:
            lines.append(" ".join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
    if current_line:
        lines.append(" ".join(current_line))

    for line in lines[:4]:
        draw.text((60, y_offset), line, font=DEFAULT_FONT, fill=(33, 33, 33))
        y_offset += 90

    draw.text((60, 820), price_text, font=DEFAULT_FONT, fill=(209, 46, 46))
    draw.text((60, 900), "Link in bio", font=SMALL_FONT, fill=(60, 60, 60))

    canvas.save(out_path, format="PNG")
    return out_path
