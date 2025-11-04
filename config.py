"""Configuration management for the RFD deal pipeline."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Strongly-typed settings loaded from environment variables.

    Attributes expose application behaviour toggles and defaults for scraping,
    content generation and output paths. Values are resolved once during
    module import so consumers can rely on immutability.
    """

    rfd_base_url: str = "https://forums.redflagdeals.com/"
    scrape_max_pages: int = 5
    rate_min_ms: int = 1000
    rate_max_ms: int = 3000
    affiliate_tag: str = "thatmarcus-20"
    data_dir: Path = Path("data")
    assets_dir: Path = Path("assets")
    use_playwright: bool = True
    generate_card_images: bool = True
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 RFDDealsBot"
    )

    @staticmethod
    def from_env(env_path: Optional[Path] = None) -> "Settings":
        """Create settings by loading environment variables from .env.

        Args:
            env_path: Optional explicit path to the `.env` file. When omitted,
                python-dotenv attempts to locate the file automatically.

        Returns:
            A populated :class:`Settings` instance.
        """

        if env_path is not None:
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()

        def _get_bool(name: str, default: bool) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        def _get_int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        data_dir = Path(os.getenv("DATA_DIR", "data"))
        assets_dir = Path(os.getenv("ASSETS_DIR", "assets"))

        return Settings(
            rfd_base_url=os.getenv("RFD_BASE_URL", Settings.rfd_base_url),
            scrape_max_pages=_get_int("SCRAPE_MAX_PAGES", Settings.scrape_max_pages),
            rate_min_ms=_get_int("RATE_MIN_MS", Settings.rate_min_ms),
            rate_max_ms=_get_int("RATE_MAX_MS", Settings.rate_max_ms),
            affiliate_tag=os.getenv("AFFILIATE_TAG", Settings.affiliate_tag),
            data_dir=data_dir,
            assets_dir=assets_dir,
            use_playwright=_get_bool("USE_PLAYWRIGHT", Settings.use_playwright),
            generate_card_images=_get_bool(
                "GENERATE_CARD_IMAGES", Settings.generate_card_images
            ),
            user_agent=os.getenv("SCRAPER_USER_AGENT", Settings.user_agent),
        )


SETTINGS = Settings.from_env()
