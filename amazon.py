"""Amazon.ca mapping helpers and affiliate tag utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from config import SETTINGS
from models import AmazonInfo


@dataclass
class AmazonSearchResult:
    asin: Optional[str]
    title: Optional[str]
    price: Optional[float]
    product_url: Optional[str]
    approximate_match: bool = False


def is_amazon_ca(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.netloc.lower().endswith("amazon.ca")


def extract_asin_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    segments = [seg for seg in parsed.path.split("/") if seg]
    for idx, seg in enumerate(segments):
        if seg.lower() in {"dp", "gp", "product"} and idx + 1 < len(segments):
            candidate = segments[idx + 1]
            return candidate[:10]
        if len(seg) == 10 and seg.isalnum():
            return seg
    query = dict(parse_qsl(parsed.query))
    asin = query.get("asin")
    if asin:
        return asin[:10]
    return None


def apply_affiliate_tag(url: str, tag: str = SETTINGS.affiliate_tag) -> str:
    """Ensure the Amazon.ca link carries the configured affiliate tag."""

    if not url or not is_amazon_ca(url):
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["tag"] = tag
    for unwanted in ["linkCode", "creativeASIN", "ascsubtag"]:
        query.pop(unwanted, None)
    new_query = urlencode(query, doseq=True)
    normalized_path = parsed.path.replace("//", "/")
    rebuilt = urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc,
            normalized_path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )
    return rebuilt


def choose_best_amazon_link(links: Sequence[str]) -> Optional[str]:
    product_like = [link for link in links if "/dp/" in link or "/gp/product/" in link]
    if product_like:
        return product_like[0]
    for link in links:
        if is_amazon_ca(link):
            return link
    return None


def search_amazon_ca(product_name: str, hints: Optional[Sequence[str]] = None) -> AmazonSearchResult:
    """Best-effort product resolution.

    The implementation intentionally avoids scraping Amazon directly. Instead
    it attempts to reuse any Amazon links discovered in the source material or
    returns a placeholder response that downstream systems can enrich via the
    Product Advertising API or other compliant data sources.
    """

    hints = hints or []
    link = choose_best_amazon_link(hints)
    if link:
        asin = extract_asin_from_url(link)
        affiliate_link = apply_affiliate_tag(link)
        return AmazonSearchResult(
            asin=asin,
            title=product_name,
            price=None,
            product_url=affiliate_link,
            approximate_match=False,
        )
    return AmazonSearchResult(
        asin=None,
        title=product_name,
        price=None,
        product_url=None,
        approximate_match=True,
    )


def build_amazon_info(result: AmazonSearchResult) -> AmazonInfo:
    domain_ok = bool(result.product_url and is_amazon_ca(result.product_url))
    affiliate_link = result.product_url
    if affiliate_link and domain_ok:
        affiliate_link = apply_affiliate_tag(affiliate_link)
    return AmazonInfo(
        asin=result.asin,
        title=result.title,
        affiliate_link=affiliate_link,
        approximate_match=result.approximate_match,
        domain_ok=domain_ok,
    )
