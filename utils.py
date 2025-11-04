"""Utility helpers shared across the RFD pipeline."""
from __future__ import annotations

import csv
import json
import random
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from html import unescape
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional, Sequence, Tuple, TypeVar

from bs4 import BeautifulSoup

from models import RetryState

T = TypeVar("T")

PRICE_PATTERN = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{2})?)")
PERCENT_PATTERN = re.compile(r"([0-9]{1,3})\s?%")
SUSPICIOUS_SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "goo.gl",
    "ow.ly",
    "rb.gy",
    "t.co",
    "is.gd",
}
GENERIC_TITLE_PATTERN = re.compile(r"^(?:best|top|mega|super|ultimate|hot) deal", re.I)


def strip_html(html: str) -> str:
    """Remove HTML tags and normalise whitespace."""

    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ")
    return normalize_whitespace(text)


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace, trim and decode HTML entities."""

    if text is None:
        return ""
    return re.sub(r"\s+", " ", unescape(text)).strip()


def slugify(value: str, max_length: int = 60) -> str:
    """Create a filesystem-friendly slug."""

    if not value:
        return "item"
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        value = "item"
    return value[:max_length]


def parse_prices(text: str) -> Sequence[float]:
    """Extract all CAD prices present in the text."""

    if not text:
        return []
    prices = []
    for match in PRICE_PATTERN.findall(text):
        try:
            prices.append(float(match))
        except ValueError:
            continue
    return prices


def parse_first_price(text: str) -> Optional[float]:
    prices = parse_prices(text)
    return prices[0] if prices else None


def parse_regular_price(text: str) -> Optional[float]:
    """Heuristic to find regular price referencing keywords."""

    if not text:
        return None
    lowered = text.lower()
    segments = re.split(r"[\.;\n]", text)
    for seg in segments:
        if any(keyword in seg.lower() for keyword in {"reg", "regular", "was", "list price", "msrp"}):
            price = parse_first_price(seg)
            if price:
                return price
    if "save" in lowered or "%" in text:
        perc = parse_first_percent(text)
        deal = parse_first_price(text)
        if perc and deal:
            return round(deal / (1 - perc / 100), 2)
    return None


def parse_first_percent(text: str) -> Optional[float]:
    if not text:
        return None
    match = PERCENT_PATTERN.search(text)
    if not match:
        return None
    return float(match.group(1))


def compute_savings(deal_price: Optional[float], regular_price: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    """Compute savings amount and percentage."""

    if deal_price is None or regular_price is None:
        return None, None
    if regular_price <= 0:
        return None, None
    savings = round(regular_price - deal_price, 2)
    if savings <= 0:
        return None, None
    percent = round((savings / regular_price) * 100, 2)
    return savings, percent


def ensure_iso_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_datetime(text: str) -> Optional[datetime]:
    """Parse common forum datetime formats."""

    if not text:
        return None
    text = normalize_whitespace(text)
    for fmt in ("%b %d, %Y %I:%M %p", "%b %dth, %Y %I:%M %p", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def json_dump(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_csv(rows: Iterable[Sequence[Any]], headers: Sequence[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def retry(max_attempts: int = 3, backoff_factor: float = 1.5) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            state = RetryState()
            delay = 1.0
            for attempt in range(1, max_attempts + 1):
                state.attempts = attempt
                state.last_attempt_at = datetime.now(timezone.utc)
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    state.last_exception = exc
                    if attempt >= max_attempts:
                        raise
                    time.sleep(delay)
                    delay *= backoff_factor
            raise RuntimeError("Retry failed")

        return wrapper

    return decorator


@contextmanager
def rate_limiter(min_ms: int, max_ms: int) -> Iterator[None]:
    """Context manager applying jittered sleep between calls."""

    start = time.monotonic()
    yield
    elapsed = time.monotonic() - start
    sleep_for = max(0.0, random.uniform(min_ms, max_ms) / 1000 - elapsed)
    if sleep_for > 0:
        time.sleep(sleep_for)


def detect_suspicious_url(url: str) -> bool:
    if not url:
        return False
    return any(shortener in url.lower() for shortener in SUSPICIOUS_SHORTENERS)


def is_price_too_good(deal_price: Optional[float], regular_price: Optional[float]) -> bool:
    if deal_price is None or regular_price is None:
        return False
    if regular_price <= 0:
        return False
    return (regular_price - deal_price) / regular_price >= 0.8


def looks_generic_title(title: str) -> bool:
    if not title:
        return False
    return bool(GENERIC_TITLE_PATTERN.search(title.strip().lower()))


def safe_join_url(base: str, path: str) -> str:
    if path.startswith("http"):
        return path
    if not base.endswith("/"):
        base += "/"
    return base + path.lstrip("/")


def iter_chunks(iterable: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for idx in range(0, len(iterable), size):
        yield iterable[idx : idx + size]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def within_days(dt: datetime, days: int) -> bool:
    return utcnow() - dt <= timedelta(days=days)
