#!/usr/bin/env python3
"""
Astroman Product Scout — Daily product finder.
Scrapes Alibaba + DHgate → AI ranks into 3 sections → sends via Telegram.

Sections:
  🔥 3 Viral products   — TikTok/social media potential
  🔭 5 Astroman picks   — astronomy/space shop relevant
  🏆 2 Bestsellers      — highest proven demand
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from scraper import scrape_all_categories
from ranker import rank_products_structured, rank_products_fallback
from notifier import send_daily_digest, send_error_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("astroman-scout")


def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def get_config():
    return {
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "openai_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "session_label": os.environ.get("SESSION_LABEL", ""),
    }


def save_results(ranked, filename=None):
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    if not filename:
        ts = datetime.now().strftime('%Y-%m-%d_%H%M')
        filename = f"products_{ts}.json"
    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(ranked, f, ensure_ascii=False, indent=2)
    logger.info(f"Results saved to {filepath}")
    return filepath


def print_ranked(ranked):
    labels = {
        "viral":       "🔥 VIRAL (3 products)",
        "astroman":    "🔭 ASTROMAN PICKS (5 products)",
        "bestsellers": "🏆 BESTSELLERS (2 products)",
    }
    for key, title in labels.items():
        products = ranked.get(key, [])
        if not products:
            continue
        print(f"\n{'=' * 60}")
        print(title)
        print('=' * 60)
        for i, p in enumerate(products, 1):
            print(f"\n{i}. {p.get('name', 'N/A')[:70]}")
            print(f"   Price:  {p.get('price', 'N/A')}")
            print(f"   Source: {p.get('source', 'N/A')} | Category: {p.get('category', 'N/A')}")
            if p.get("score"):
                print(f"   Score:  {p['score']}/100")
            if p.get("reason"):
                print(f"   Why:    {p['reason']}")
            if p.get("orders_or_reviews"):
                print(f"   Orders: {p['orders_or_reviews']}")
            print(f"   Link:   {p.get('link', 'N/A')}")
    print(f"\n{'=' * 60}\n")


async def run(args):
    config = get_config()
    session_label = args.session_label or config["session_label"]

    # Step 1: Scrape
    logger.info("Scraping products from Alibaba + DHgate...")
    try:
        products = await scrape_all_categories()
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        if config["telegram_bot_token"] and config["telegram_chat_id"]:
            send_error_alert(f"Scraping failed: {e}", config["telegram_bot_token"], config["telegram_chat_id"])
        sys.exit(1)

    logger.info(f"Found {len(products)} products total")

    if not products:
        logger.warning("No products found. Exiting.")
        if config["telegram_bot_token"] and config["telegram_chat_id"]:
            send_error_alert("No products found this session.", config["telegram_bot_token"], config["telegram_chat_id"])
        sys.exit(0)

    if args.scrape_only:
        print_ranked({"astroman": [p.to_dict() for p in products[:20]]})
        save_results({"raw": [p.to_dict() for p in products]}, "scrape_raw.json")
        return

    # Step 2: Rank with AI into 3 sections
    logger.info("Ranking with AI → 3 viral, 5 astroman, 2 bestsellers...")
    if config["openai_api_key"]:
        ranked = rank_products_structured(products, config["openai_api_key"], model=config["openai_model"])
        # Fall back to heuristic if AI returned empty sections
        total = sum(len(v) for v in ranked.values())
        if total == 0:
            logger.warning("AI ranking returned empty, using fallback")
            ranked = rank_products_fallback(products)
    else:
        logger.warning("No OPENAI_API_KEY — using fallback ranking")
        ranked = rank_products_fallback(products)

    print_ranked(ranked)
    save_results(ranked)

    if args.dry_run:
        logger.info("Dry run — skipping Telegram notification")
        return

    # Step 3: Send via Telegram
    if config["telegram_bot_token"] and config["telegram_chat_id"]:
        logger.info("Sending Telegram digest...")
        success = send_daily_digest(ranked, config["telegram_bot_token"], config["telegram_chat_id"], session_label=session_label)
        if success:
            logger.info("Digest sent successfully!")
        else:
            logger.error("Failed to send Telegram digest")
    else:
        logger.warning("Telegram credentials not set. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Astroman Product Scout")
    parser.add_argument("--scrape-only", action="store_true", help="Just scrape, don't rank or notify")
    parser.add_argument("--dry-run", action="store_true", help="Scrape + rank but don't send Telegram")
    parser.add_argument("--session-label", type=str, default="", help="Session label (noon/evening)")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
