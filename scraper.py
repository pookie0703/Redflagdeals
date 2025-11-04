"""Scraper for RedFlagDeals Amazon threads."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from config import SETTINGS
from models import RawPost, ScrapeConfig
from utils import ensure_iso_datetime, parse_datetime, rate_limiter, safe_join_url, strip_html, within_days

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover - runtime check
    PLAYWRIGHT_AVAILABLE = False


class RFDScraper:
    """Scrape RedFlagDeals hot deals forum for Amazon-related posts."""

    def __init__(self, config: ScrapeConfig, use_playwright: Optional[bool] = None):
        self.config = config
        if use_playwright is None:
            use_playwright = SETTINGS.use_playwright
        self.use_playwright = use_playwright and PLAYWRIGHT_AVAILABLE
        if use_playwright and not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright requested but unavailable; falling back to requests")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": SETTINGS.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def scrape(self, max_posts: int, days: int) -> List[RawPost]:
        logger.info("Starting scrape: max_posts=%s days=%s", max_posts, days)
        posts: List[RawPost] = []
        if self.use_playwright:
            try:
                posts = self._scrape_with_playwright(max_posts, days)
            except Exception as exc:  # pragma: no cover - degrade gracefully
                logger.error("Playwright scrape failed, falling back to requests: %s", exc)
                posts = self._scrape_with_requests(max_posts, days)
        else:
            posts = self._scrape_with_requests(max_posts, days)
        logger.info("Scrape complete: %s posts", len(posts))
        return posts[:max_posts]

    # ------------------------------------------------------------------
    def _scrape_with_requests(self, max_posts: int, days: int) -> List[RawPost]:
        posts: List[RawPost] = []
        page = 0
        seen_urls: set[str] = set()
        while len(posts) < max_posts and page < self.config.max_pages:
            page_url = self._page_url(page)
            logger.debug("Fetching forum page: %s", page_url)
            with rate_limiter(self.config.min_delay_ms, self.config.max_delay_ms):
                response = self.session.get(page_url, timeout=self.config.request_timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            thread_links = soup.select(self.config.selectors["thread_title"])
            if not thread_links:
                logger.debug("No threads found on page %s", page_url)
                break
            for link in thread_links:
                title = strip_html(link.get_text())
                href = link.get("href") or ""
                thread_url = safe_join_url(self.config.base_url, href)
                if thread_url in seen_urls:
                    continue
                seen_urls.add(thread_url)
                if not self._is_amazon_thread(title):
                    continue
                thread_post = self._fetch_thread(thread_url)
                if not thread_post:
                    continue
                posted_at_iso = thread_post.get("posted_at")
                if posted_at_iso:
                    try:
                        posted_dt = datetime.fromisoformat(posted_at_iso.replace("Z", "+00:00"))
                    except ValueError:
                        posted_dt = None
                    if posted_dt and not within_days(posted_dt, days):
                        logger.debug("Skipping thread outside window: %s", thread_url)
                        continue
                posts.append(thread_post)
                if len(posts) >= max_posts:
                    break
            page += 1
        return posts

    def _fetch_thread(self, thread_url: str) -> Optional[RawPost]:
        logger.debug("Fetching thread: %s", thread_url)
        with rate_limiter(self.config.min_delay_ms, self.config.max_delay_ms):
            response = self.session.get(thread_url, timeout=self.config.request_timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        post_container = soup.select_one(self.config.selectors["post_container"])
        if not post_container:
            logger.debug("No post container found for %s", thread_url)
            return None
        title = soup.find("h1")
        if title:
            title_text = strip_html(title.get_text())
        else:
            title_text = ""
        content = post_container.select_one(self.config.selectors["post_content"])
        body_html = content.decode() if content else post_container.decode()
        body_text = strip_html(body_html)

        author_tag = post_container.select_one(self.config.selectors["post_author"])
        author = strip_html(author_tag.get_text()) if author_tag else ""
        date_tag = post_container.select_one(self.config.selectors["post_date"])
        posted_at = parse_datetime(strip_html(date_tag.get_text()) if date_tag else "")
        if not posted_at:
            posted_at = datetime.now(timezone.utc)
        score_tag = post_container.select_one(self.config.selectors["post_score"])
        score = None
        if score_tag:
            try:
                score = int(strip_html(score_tag.get_text()))
            except ValueError:
                score = None

        outbound_links = [a.get("href") for a in post_container.select("a[href]")]

        return RawPost(
            title=title_text,
            url=thread_url,
            posted_at=ensure_iso_datetime(posted_at),
            author=author,
            body_html=body_html,
            body_text=body_text,
            score=score,
            comments=self._extract_thread_metric(soup, "Replies"),
            views=self._extract_thread_metric(soup, "Views"),
            outbound_links=[link for link in outbound_links if link],
        )

    def _extract_thread_metric(self, soup: BeautifulSoup, label: str) -> Optional[int]:
        label_el = soup.find(string=lambda text: text and label in text)
        if not label_el:
            return None
        try:
            return int("".join(ch for ch in label_el if ch.isdigit()))
        except ValueError:
            return None

    def _scrape_with_playwright(self, max_posts: int, days: int) -> List[RawPost]:  # pragma: no cover - network heavy
        posts: List[RawPost] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=SETTINGS.user_agent)
            current_page = 0
            seen_urls: set[str] = set()
            while len(posts) < max_posts and current_page < self.config.max_pages:
                listing_url = self._page_url(current_page)
                logger.debug("Playwright visiting: %s", listing_url)
                page.goto(listing_url, wait_until="networkidle")
                thread_handles = page.query_selector_all(self.config.selectors["thread_title"])
                for handle in thread_handles:
                    title = (handle.inner_text() or "").strip()
                    href = handle.get_attribute("href") or ""
                    thread_url = safe_join_url(self.config.base_url, href)
                    if thread_url in seen_urls:
                        continue
                    seen_urls.add(thread_url)
                    if not self._is_amazon_thread(title):
                        continue
                    page.goto(thread_url, wait_until="networkidle")
                    html = page.content()
                    soup = BeautifulSoup(html, "lxml")
                    post = self._parse_thread_soup(thread_url, soup)
                    if post:
                        posted_at_iso = post.get("posted_at")
                        if posted_at_iso:
                            try:
                                posted_dt = datetime.fromisoformat(posted_at_iso.replace("Z", "+00:00"))
                            except ValueError:
                                posted_dt = None
                            if posted_dt and not within_days(posted_dt, days):
                                continue
                        posts.append(post)
                        if len(posts) >= max_posts:
                            break
                current_page += 1
            browser.close()
        return posts

    def _parse_thread_soup(self, thread_url: str, soup: BeautifulSoup) -> Optional[RawPost]:
        post_container = soup.select_one(self.config.selectors["post_container"])
        if not post_container:
            return None
        title = soup.find("h1")
        title_text = strip_html(title.get_text()) if title else ""
        content = post_container.select_one(self.config.selectors["post_content"])
        body_html = content.decode() if content else post_container.decode()
        body_text = strip_html(body_html)
        author_tag = post_container.select_one(self.config.selectors["post_author"])
        author = strip_html(author_tag.get_text()) if author_tag else ""
        date_tag = post_container.select_one(self.config.selectors["post_date"])
        posted_at = parse_datetime(strip_html(date_tag.get_text()) if date_tag else "")
        if not posted_at:
            posted_at = datetime.now(timezone.utc)
        score_tag = post_container.select_one(self.config.selectors["post_score"])
        score = None
        if score_tag:
            try:
                score = int(strip_html(score_tag.get_text()))
            except ValueError:
                score = None
        outbound_links = [a.get("href") for a in post_container.select("a[href]")]
        return RawPost(
            title=title_text,
            url=thread_url,
            posted_at=ensure_iso_datetime(posted_at),
            author=author,
            body_html=body_html,
            body_text=body_text,
            score=score,
            comments=self._extract_thread_metric(soup, "Replies"),
            views=self._extract_thread_metric(soup, "Views"),
            outbound_links=[link for link in outbound_links if link],
        )

    def _page_url(self, page_number: int) -> str:
        if page_number == 0:
            return safe_join_url(self.config.base_url, self.config.hot_deals_path)
        offset = page_number * 40
        return safe_join_url(self.config.base_url, f"{self.config.hot_deals_path}?st={offset}")

    def _is_amazon_thread(self, title: str) -> bool:
        return "amazon" in (title or "").lower()


def create_default_scraper() -> RFDScraper:
    cfg = ScrapeConfig(
        base_url=SETTINGS.rfd_base_url,
        max_pages=SETTINGS.scrape_max_pages,
        min_delay_ms=SETTINGS.rate_min_ms,
        max_delay_ms=SETTINGS.rate_max_ms,
        user_agent=SETTINGS.user_agent,
    )
    return RFDScraper(cfg)
