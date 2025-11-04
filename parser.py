"""Deal extraction and normalization from raw RFD posts."""
from __future__ import annotations

import re
from html import unescape
from typing import Iterable, List

from bs4 import BeautifulSoup

from models import DealSummary, RawPost
from utils import (
    compute_savings,
    normalize_whitespace,
    parse_first_price,
    parse_regular_price,
    strip_html,
)

BRACKETED_PATTERN = re.compile(r"\[[^\]]+\]")
EMOJI_PATTERN = re.compile(
    "[\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "]",
    flags=re.UNICODE,
)


def clean_title(title: str) -> str:
    title = normalize_whitespace(title)
    title = BRACKETED_PATTERN.sub("", title)
    title = EMOJI_PATTERN.sub("", title)
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"\s+[-|]\s+", " ", title)
    return normalize_whitespace(title)


def extract_amazon_links(post: RawPost) -> List[str]:
    links: List[str] = []
    html = post.get("body_html") or ""
    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if href and "amazon.ca" in href:
            links.append(unescape(href))
    for link in post.get("outbound_links", []) or []:
        if "amazon.ca" in link:
            links.append(link)
    return list(dict.fromkeys(links))


def product_name_from_post(post: RawPost) -> str:
    title = post.get("title") or "Amazon.ca Deal"
    cleaned = clean_title(title)
    if cleaned:
        return cleaned
    body_text = post.get("body_text") or ""
    return normalize_whitespace(body_text[:120])


def determine_seller(text: str, amazon_links: Iterable[str]) -> str:
    text_lower = text.lower()
    if "fulfilled by amazon" in text_lower:
        match = re.search(r"sold by ([^.,]+)", text_lower)
        if match:
            return normalize_whitespace(match.group(1).title())
        return "Sold by third-party, Fulfilled by Amazon"
    if amazon_links:
        return "Amazon.ca"
    return "Unknown"


def build_deal_summary(post: RawPost) -> DealSummary:
    body_text = post.get("body_text") or strip_html(post.get("body_html", ""))
    joined_text = f"{post.get('title', '')}. {body_text}"
    deal_price = parse_first_price(joined_text)
    regular_price = parse_regular_price(joined_text)
    if regular_price and deal_price and regular_price < deal_price:
        regular_price = None
    savings_amount, savings_percent = compute_savings(deal_price, regular_price)
    amazon_links = extract_amazon_links(post)
    seller = determine_seller(joined_text, amazon_links)

    return DealSummary(
        product_name=product_name_from_post(post),
        deal_price=deal_price,
        regular_price=regular_price,
        savings_amount=savings_amount,
        savings_percent=savings_percent,
        seller=seller,
        source_url=post.get("url", ""),
        deal_date=post.get("posted_at", ""),
        forum_popularity={
            "score": post.get("score"),
            "comments": post.get("comments"),
            "views": post.get("views"),
        },
        amazon_links=amazon_links,
    )


if __name__ == "__main__":
    sample_posts: List[RawPost] = [
        RawPost(
            title="[Amazon] Anker USB-C Charger 65W - $39.99 (Reg $59.99)",
            url="https://forums.redflagdeals.com/thread1",
            posted_at="2024-05-01T12:00:00Z",
            author="dealhunter",
            body_html='<p>Solid charger from Anker. Amazon link <a href="https://www.amazon.ca/dp/B08XYZ">here</a>.</p>',
            body_text="Solid charger from Anker. Amazon link here.",
            score=120,
            comments=34,
            views=5600,
            outbound_links=["https://www.amazon.ca/dp/B08XYZ"],
        ),
        RawPost(
            title="Lightning deal: Noise Cancelling Headphones",
            url="https://forums.redflagdeals.com/thread2",
            posted_at="2024-05-02T10:00:00Z",
            author="bargainlover",
            body_html="<p>Drop from $199 to $99 today only. Sold by BrandX on Amazon.</p>",
            body_text="Drop from $199 to $99 today only. Sold by BrandX on Amazon.",
            score=80,
            comments=20,
            views=4000,
            outbound_links=[],
        ),
    ]

    for sample in sample_posts:
        summary = build_deal_summary(sample)
        print(summary)
