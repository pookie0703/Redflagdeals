"""CLI entry point for the RFD Amazon deal pipeline."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import SETTINGS
from pipeline import normalize_and_map, scrape_to_json, social_from_json

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RFD Amazon deals automation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape_parser = subparsers.add_parser("scrape", help="Scrape raw forum posts")
    scrape_parser.add_argument("--max-posts", type=int, default=50, dest="max_posts")
    scrape_parser.add_argument("--days", type=int, default=2)
    scrape_parser.add_argument("--out", type=Path, required=True)

    process_parser = subparsers.add_parser("process", help="Normalize raw posts")
    process_parser.add_argument("in_json", type=Path)
    process_parser.add_argument("out_json", type=Path)

    social_parser = subparsers.add_parser("social", help="Generate social captions/assets")
    social_parser.add_argument("in_json", type=Path)
    social_parser.add_argument("out_csv", type=Path)
    social_parser.add_argument("--assets", type=Path, default=SETTINGS.assets_dir)

    return parser.parse_args(argv)


def cmd_scrape(args: argparse.Namespace) -> int:
    try:
        scrape_to_json(args.out, max_posts=args.max_posts, days=args.days, cfg=None)
        return 0
    except Exception as exc:  # pragma: no cover - CLI guard
        logger.exception("Scrape failed: %s", exc)
        return 1


def cmd_process(args: argparse.Namespace) -> int:
    try:
        deals = normalize_and_map(args.in_json, args.out_json)
        affiliate_count = sum(
            1 for deal in deals if deal.get("amazon", {}).get("affiliate_link")
        )
        logger.info(
            "Processed %s deals (affiliate links: %s)",
            len(deals),
            affiliate_count,
        )
        return 0
    except Exception as exc:  # pragma: no cover - CLI guard
        logger.exception("Process failed: %s", exc)
        return 2


def cmd_social(args: argparse.Namespace) -> int:
    try:
        social_from_json(args.in_json, args.out_csv, args.assets)
        logger.info("Social assets generated")
        return 0
    except Exception as exc:  # pragma: no cover - CLI guard
        logger.exception("Social generation failed: %s", exc)
        return 3


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "scrape":
        return cmd_scrape(args)
    if args.command == "process":
        return cmd_process(args)
    if args.command == "social":
        return cmd_social(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
