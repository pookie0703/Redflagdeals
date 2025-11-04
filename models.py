"""Typed structures shared across the RFD pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, TypedDict


class RawPost(TypedDict, total=False):
    """Representation of a scraped forum post."""

    title: str
    url: str
    posted_at: str
    author: str
    body_html: str
    body_text: str
    score: Optional[int]
    comments: Optional[int]
    views: Optional[int]
    outbound_links: List[str]


class DealSummary(TypedDict, total=False):
    product_name: str
    deal_price: Optional[float]
    regular_price: Optional[float]
    savings_amount: Optional[float]
    savings_percent: Optional[float]
    seller: str
    source_url: str
    deal_date: str
    forum_popularity: "ForumPopularity"
    amazon_links: List[str]


class ForumPopularity(TypedDict, total=False):
    score: Optional[int]
    comments: Optional[int]
    views: Optional[int]


class AmazonInfo(TypedDict, total=False):
    asin: Optional[str]
    title: Optional[str]
    affiliate_link: Optional[str]
    approximate_match: bool
    domain_ok: bool


class SocialInfo(TypedDict, total=False):
    caption: str
    hashtags: str
    asset_path: Optional[str]


class FlagsInfo(TypedDict, total=False):
    possible_scam: bool
    weak_reviews: bool
    inauthentic_listing: bool
    notes: str


class NormalizedDeal(TypedDict, total=False):
    deal_summary: DealSummary
    amazon: AmazonInfo
    social: SocialInfo
    flags: FlagsInfo


@dataclass
class ScrapeConfig:
    """Scraping configuration for RFD threads."""

    base_url: str
    hot_deals_path: str = "hot-deals-f9"
    max_pages: int = 5
    min_delay_ms: int = 1000
    max_delay_ms: int = 3000
    request_timeout: int = 20
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 RFDDealsBot"
    )
    selectors: dict = field(
        default_factory=lambda: {
            "thread_rows": "#threadlist tbody tr",
            "thread_title": "a.topic_title",
            "thread_meta": "td.topic_meta",
            "thread_views": "td.topic_views",
            "thread_replies": "td.topic_replies",
            "post_container": "div.postbody",
            "post_content": "div.content",
            "post_author": "a.username",
            "post_date": "span.post-time",
            "post_score": "span.vote-count",
        }
    )


@dataclass
class RetryState:
    attempts: int = 0
    last_exception: Optional[Exception] = None
    last_attempt_at: Optional[datetime] = None
