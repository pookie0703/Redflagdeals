"""Risk and quality heuristics for scraped deals."""
from __future__ import annotations

from typing import Dict, Iterable

from models import FlagsInfo
from utils import detect_suspicious_url, is_price_too_good, looks_generic_title

SCAM_KEYWORDS = {"e-transfer", "etransfer", "whatsapp", "outside platform", "telegram"}


def assess_flags(
    *,
    title: str,
    body_text: str,
    outbound_links: Iterable[str],
    deal_price: float | None,
    regular_price: float | None,
) -> FlagsInfo:
    """Compute heuristic flags for a deal."""

    notes: list[str] = []
    possible_scam = False
    text = f"{title} {body_text}".lower()
    if any(keyword in text for keyword in SCAM_KEYWORDS):
        possible_scam = True
        notes.append("Contains potential off-platform contact/payment keywords")
    if any(detect_suspicious_url(link) for link in outbound_links):
        possible_scam = True
        notes.append("Contains suspicious short link")

    weak_reviews = False  # Placeholder for future integrations.

    inauthentic_listing = False
    if looks_generic_title(title):
        inauthentic_listing = True
        notes.append("Title looks overly generic")
    if is_price_too_good(deal_price, regular_price):
        inauthentic_listing = True
        notes.append("Discount exceeds 80% of regular price")

    return FlagsInfo(
        possible_scam=possible_scam,
        weak_reviews=weak_reviews,
        inauthentic_listing=inauthentic_listing,
        notes="; ".join(notes),
    )
