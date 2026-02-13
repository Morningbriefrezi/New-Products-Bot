#!/usr/bin/env python3
"""
Alibaba Scout — Daily viral product finder.
Scrapes Chinese wholesale suppliers → ranks with OpenAI → sends via Telegram.
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
from ranker import rank_products, rank_products_fallback
from notifier import send_daily_digest, send_error_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("alibaba-scout")


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
        "product_count": int(os.environ.get("PRODUCT_COUNT", "5")),
        "session_label": os.environ.get("SESSION_LABEL", ""),
    }


def save_results(products, filename=None):
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    if not filename:
        ts = datetime.now().strftime('%Y-%m-%d_%H%M')
        filename = f"products_{ts}.json"
    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    logger.info(f"Results saved to {filepath}")
    return filepath


def print_products(products):
    print("\n" + "=" * 60)
    print(f"TOP {len(products)} VIRAL PRODUCTS")
    print("=" * 60)
    for i, p in enumerate(products, 1):
        print(f"\n{i}. {p.get('name', 'N/A')[:70]}")
        print(f"   Price: {p.get('price', 'N/A')}")
        print(f"   Source: {p.get('source', 'N/A')} | Category: {p.get('category', 'N/A')}")
        if p.get("score"):
            print(f"   Score: {p['score']}/100")
        if p.get("reason"):
            print(f"   Why: {p['reason']}")
        print(f"   Link: {p.get('link', 'N/A')}")
    print("\n" + "=" * 60)


async def run(args):
    config = get_config()
    count = args.count or config["product_count"]
    session_label = args.session_label or config["session_label"]

    # Step 1: Scrape
    logger.info(f"Scraping products (need top {count})...")
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
        print_products([p.to_dict() for p in products[:20]])
        save_results([p.to_dict() for p in products], "scrape_raw.json")
        return

    # Step 2: Rank with OpenAI
    logger.info(f"Ranking products with AI (selecting top {count})...")
    if config["openai_api_key"]:
        top_products = rank_products(products, config["openai_api_key"], model=config["openai_model"], top_n=count)
        if not top_products:
            logger.warning("OpenAI ranking returned empty, using fallback")
            top_products = rank_products_fallback(products, top_n=count)
    else:
        logger.warning("No OPENAI_API_KEY set, using fallback ranking")
        top_products = rank_products_fallback(products, top_n=count)

    print_products(top_products)
    save_results(top_products)

    if args.dry_run:
        logger.info("Dry run - skipping Telegram notification")
        return

    # Step 3: Send via Telegram
    if config["telegram_bot_token"] and config["telegram_chat_id"]:
        logger.info("Sending Telegram digest...")
        success = send_daily_digest(top_products, config["telegram_bot_token"], config["telegram_chat_id"], session_label=session_label)
        if success:
            logger.info("Digest sent!")
        else:
            logger.error("Failed to send Telegram digest")
    else:
        logger.warning("Telegram credentials not set. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Alibaba Scout")
    parser.add_argument("--scrape-only", action="store_true", help="Just scrape, don't rank or notify")
    parser.add_argument("--dry-run", action="store_true", help="Scrape + rank but don't send Telegram")
    parser.add_argument("--count", type=int, default=None, help="Number of products (default: 5)")
    parser.add_argument("--session-label", type=str, default="", help="Session label (noon/evening)")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
