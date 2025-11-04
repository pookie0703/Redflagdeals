"""Pipeline composition for scraping, normalization and social generation."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from amazon import build_amazon_info, search_amazon_ca
from config import SETTINGS
from flags import assess_flags
from models import NormalizedDeal, RawPost, ScrapeConfig
from parser import build_deal_summary
from scraper import RFDScraper
from social import generate_caption, render_card_image
from utils import json_dump, json_load, slugify, write_csv

logger = logging.getLogger(__name__)


def scrape_to_json(out_path: Path, max_posts: int, days: int, cfg: ScrapeConfig | None = None) -> List[RawPost]:
    cfg = cfg or ScrapeConfig(
        base_url=SETTINGS.rfd_base_url,
        max_pages=SETTINGS.scrape_max_pages,
        min_delay_ms=SETTINGS.rate_min_ms,
        max_delay_ms=SETTINGS.rate_max_ms,
        user_agent=SETTINGS.user_agent,
    )
    scraper = RFDScraper(cfg)
    posts = scraper.scrape(max_posts=max_posts, days=days)
    json_dump(posts, out_path)
    logger.info("Saved %s raw posts to %s", len(posts), out_path)
    return posts


def normalize_and_map(in_path: Path, out_path: Path, cfg: ScrapeConfig | None = None) -> List[NormalizedDeal]:
    raw_posts: List[RawPost] = json_load(in_path)
    normalized: List[NormalizedDeal] = []
    for post in raw_posts:
        summary = build_deal_summary(post)
        amazon_result = search_amazon_ca(summary["product_name"], summary.get("amazon_links", []))
        amazon_info = build_amazon_info(amazon_result)
        flags = assess_flags(
            title=summary.get("product_name", ""),
            body_text=post.get("body_text", ""),
            outbound_links=post.get("outbound_links", []),
            deal_price=summary.get("deal_price"),
            regular_price=summary.get("regular_price"),
        )
        caption, hashtags = generate_caption(summary)
        normalized.append(
            NormalizedDeal(
                deal_summary=summary,
                amazon=amazon_info,
                social={"caption": caption, "hashtags": hashtags, "asset_path": None},
                flags=flags,
            )
        )
    json_dump(normalized, out_path)
    logger.info("Saved %s normalized deals to %s", len(normalized), out_path)
    return normalized


def social_from_json(in_path: Path, out_csv: Path, assets_dir: Path, cfg: ScrapeConfig | None = None) -> None:
    normalized: List[NormalizedDeal] = json_load(in_path)
    rows: List[List[str]] = []
    assets_dir.mkdir(parents=True, exist_ok=True)
    for deal in normalized:
        summary = deal.get("deal_summary", {})
        social_info = deal.get("social", {})
        caption = social_info.get("caption")
        hashtags = social_info.get("hashtags")
        asset_path = social_info.get("asset_path")
        if SETTINGS.generate_card_images and not asset_path:
            slug = slugify(summary.get("product_name") or "deal")
            filename = f"{slug}.png"
            out_path = assets_dir / filename
            try:
                render_card_image(summary, out_path)
                asset_path = str(out_path)
            except Exception as exc:  # pragma: no cover - rendering optional
                logger.warning("Failed to render image for %s: %s", slug, exc)
        rows.append([
            summary.get("product_name", ""),
            caption or "",
            hashtags or "",
            asset_path or "",
            deal.get("amazon", {}).get("affiliate_link", ""),
        ])
        deal.setdefault("social", {})["asset_path"] = asset_path
    json_dump(normalized, in_path)
    write_csv(rows, ["product_name", "caption", "hashtags", "asset_path", "affiliate_link"], out_csv)
    logger.info("Generated social CSV at %s with %s rows", out_csv, len(rows))
