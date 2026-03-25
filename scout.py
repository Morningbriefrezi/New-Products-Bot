#!/usr/bin/env python3
"""
Daily Product Scout for Astroman.ge
Scrapes Amazon BSR + eBay Top Rated in astronomy categories,
filters with Claude API, sends results to Telegram.
"""

import os
import json
import time
import random
import requests
import anthropic
from datetime import datetime
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Amazon Best Seller URLs — astronomy / optics / astrophotography
AMAZON_BSR_URLS = [
    ("Telescopes & Accessories", "https://www.amazon.com/Best-Sellers-Sports-Outdoors-Telescopes-Accessories/zgbs/sporting-goods/3400891"),
    ("Astronomy Cameras", "https://www.amazon.com/Best-Sellers-Camera-Photo-Astronomy-Cameras/zgbs/photo/3107781"),
    ("Binoculars", "https://www.amazon.com/Best-Sellers-Sports-Outdoors-Binoculars/zgbs/sporting-goods/3400851"),
    ("Night Vision", "https://www.amazon.com/Best-Sellers-Electronics-Night-Vision/zgbs/electronics/499292"),
    ("Telescope Eyepieces", "https://www.amazon.com/Best-Sellers-Sports-Outdoors-Telescope-Eyepieces/zgbs/sporting-goods/3400921"),
]

# eBay search URLs — top rated, astronomy
EBAY_SEARCH_URLS = [
    ("eBay Telescopes Top Rated", "https://www.ebay.com/sch/i.html?_nkw=telescope&_sop=12&LH_TRS=1&_ipg=20"),
    ("eBay Astrophotography Gear", "https://www.ebay.com/sch/i.html?_nkw=astrophotography+camera+mount&_sop=12&LH_TRS=1&_ipg=20"),
    ("eBay Telescope Accessories", "https://www.ebay.com/sch/i.html?_nkw=telescope+eyepiece+filter&_sop=12&LH_TRS=1&_ipg=20"),
]

ASTROMAN_CONTEXT = """
Astroman.ge is Georgia's first and only astronomy e-commerce store, based in Tbilisi.
We sell:
- Telescopes (refractor, reflector, Dobsonian, computerized/GoTo)
- Telescope mounts (alt-az, equatorial, GoTo)
- Eyepieces, Barlow lenses, filters (Moon, nebula, solar)
- Binoculars (astronomy-grade, 7x50, 10x50, 15x70)
- Astrophotography cameras (planetary, deep sky, all-sky)
- Astronomy accessories: red flashlights, planispheres, star atlases, dew heaters,
  carrying cases, finders (Telrad, red dot), collimators
- Solar observation: solar filters, Herschel wedge, H-alpha scopes
- Meteorology / weather stations (crossover audience)
- Books about astronomy (Georgian + Russian + English)

Our price range: 50–5000 GEL (~$20–$2000 USD).
Our audience: beginners to intermediate amateur astronomers in Georgia.
We do NOT sell: generic outdoor gear, hunting scopes, drone cameras, action cameras,
  security cameras, sunglasses, or anything unrelated to sky observation.
Current gap: we under-index on astrophotography accessories and GoTo mounts.
"""


def scrape_amazon_bsr(category_name: str, url: str) -> list[dict]:
    """Scrape top products from Amazon Best Sellers page."""
    products = []
    try:
        time.sleep(random.uniform(2, 4))
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [Amazon] {category_name}: HTTP {resp.status_code}")
            return products

        soup = BeautifulSoup(resp.text, "html.parser")

        # Amazon BSR uses multiple possible selectors depending on page version
        items = soup.select("div.zg-grid-general-faceout") or \
                soup.select("li.zg-item-immersion") or \
                soup.select("[data-asin]")

        for item in items[:20]:
            try:
                # Product name
                name_el = item.select_one("span.zg-bdg-text, div._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y, span.a-size-small")
                name = name_el.get_text(strip=True) if name_el else None
                if not name:
                    name_el = item.select_one("a span")
                    name = name_el.get_text(strip=True) if name_el else None

                # Price
                price_el = item.select_one("span.p13n-sc-price, span._cDEzb_p13n-sc-price_3mJ9Z")
                price = price_el.get_text(strip=True) if price_el else "N/A"

                # Rating
                rating_el = item.select_one("span.a-icon-alt")
                rating = rating_el.get_text(strip=True)[:3] if rating_el else "N/A"

                # BSR rank
                rank_el = item.select_one("span.zg-bdg-text")
                rank = rank_el.get_text(strip=True) if rank_el else "?"

                if name and len(name) > 5:
                    products.append({
                        "source": f"Amazon BSR — {category_name}",
                        "name": name[:120],
                        "price_usd": price,
                        "rating": rating,
                        "rank": rank,
                    })
            except Exception:
                continue

        print(f"  [Amazon] {category_name}: {len(products)} products")

    except Exception as e:
        print(f"  [Amazon] {category_name}: error — {e}")

    return products


def scrape_ebay_top_rated(category_name: str, url: str) -> list[dict]:
    """Scrape top-rated listings from eBay search."""
    products = []
    try:
        time.sleep(random.uniform(2, 4))
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [eBay] {category_name}: HTTP {resp.status_code}")
            return products

        soup = BeautifulSoup(resp.text, "html.parser")

        # eBay listing items
        items = soup.select("li.s-item")

        for item in items[:20]:
            try:
                name_el = item.select_one("div.s-item__title span, span.s-item__title")
                name = name_el.get_text(strip=True) if name_el else None
                if not name or name.lower() == "shop on ebay":
                    continue

                price_el = item.select_one("span.s-item__price")
                price = price_el.get_text(strip=True) if price_el else "N/A"

                rating_el = item.select_one("span.s-item__reviews-count")
                rating = rating_el.get_text(strip=True) if rating_el else ""

                sold_el = item.select_one("span.s-item__hotness, span.s-item__quantitySold")
                sold = sold_el.get_text(strip=True) if sold_el else ""

                products.append({
                    "source": f"eBay Top Rated — {category_name}",
                    "name": name[:120],
                    "price_usd": price,
                    "rating": rating,
                    "sold": sold,
                })
            except Exception:
                continue

        print(f"  [eBay] {category_name}: {len(products)} products")

    except Exception as e:
        print(f"  [eBay] {category_name}: error — {e}")

    return products


def filter_with_claude(raw_products: list[dict]) -> list[dict]:
    """Use Claude to filter & score products for Astroman relevance."""
    if not raw_products:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    product_list_text = "\n".join(
        f"{i+1}. [{p['source']}] {p['name']} | Price: {p['price_usd']} | {p.get('rating','')}"
        for i, p in enumerate(raw_products)
    )

    prompt = f"""You are a product sourcing advisor for Astroman.ge — an astronomy e-commerce store in Georgia.

STORE CONTEXT:
{ASTROMAN_CONTEXT}

SCRAPED PRODUCTS (from Amazon Best Sellers and eBay Top Rated today):
{product_list_text}

YOUR TASK:
1. Filter out any products NOT relevant to Astroman (hunting scopes, action cams, security gear, etc.)
2. Score each relevant product 1–10 on: (a) fit for Astroman catalog, (b) sourcing opportunity (can we import & resell?)
3. Add a short note: WHY it fits, suggested Georgian price range in GEL, and which customer segment (beginner / intermediate / advanced)

Return ONLY the top 8–12 products as a JSON array with this structure:
[
  {{
    "name": "product name",
    "source": "Amazon BSR / eBay",
    "price_usd": "$XX",
    "astroman_score": 8,
    "segment": "beginner",
    "why": "Short reason it fits Astroman",
    "suggested_gel_price": "XXX–XXX GEL"
  }}
]

Return ONLY the JSON array. No markdown, no explanation."""

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        # Strip any accidental markdown
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  [Claude] JSON parse error: {e}")
        print(f"  Raw response: {text[:300]}")
        return []
    except Exception as e:
        print(f"  [Claude] API error: {e}")
        return []


def format_telegram_message(products: list[dict]) -> str:
    """Format product list as a clean Telegram message."""
    today = datetime.now().strftime("%d %b %Y")
    lines = [f"🔭 *Astroman Daily Product Scout — {today}*\n"]

    if not products:
        lines.append("⚠️ No relevant products found today. Check scraper logs.")
        return "\n".join(lines)

    for i, p in enumerate(products, 1):
        score = p.get("astroman_score", "?")
        stars = "⭐" * min(int(score), 5) if isinstance(score, (int, float)) else ""
        lines.append(
            f"*{i}. {p['name']}*\n"
            f"📦 {p.get('source','')}\n"
            f"💵 {p.get('price_usd','')} → 💴 {p.get('suggested_gel_price','')}\n"
            f"👥 {p.get('segment','').capitalize()} | Score: {score}/10 {stars}\n"
            f"💡 {p.get('why','')}\n"
        )

    lines.append("─────────────────────")
    lines.append(f"_Total candidates analyzed: {len(products)}_")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """Send message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("  [Telegram] Message sent ✓")
            return True
        else:
            print(f"  [Telegram] Error {r.status_code}: {r.text[:200]}")
            # Retry without markdown if parse error
            if "parse" in r.text.lower():
                payload["parse_mode"] = "HTML"
                payload["text"] = text.replace("*", "<b>").replace("_", "<i>")
                r2 = requests.post(url, json=payload, timeout=10)
                return r2.status_code == 200
            return False
    except Exception as e:
        print(f"  [Telegram] Exception: {e}")
        return False


def main():
    print(f"\n{'='*50}")
    print(f"Daily Product Scout — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    all_raw = []

    # ── Scrape Amazon ─────────────────────────────────────────────────────────
    print("\n[1/3] Scraping Amazon Best Sellers...")
    for name, url in AMAZON_BSR_URLS:
        products = scrape_amazon_bsr(name, url)
        all_raw.extend(products)

    # ── Scrape eBay ───────────────────────────────────────────────────────────
    print("\n[2/3] Scraping eBay Top Rated...")
    for name, url in EBAY_SEARCH_URLS:
        products = scrape_ebay_top_rated(name, url)
        all_raw.extend(products)

    print(f"\n  Total raw products: {len(all_raw)}")

    # ── Deduplicate by name ───────────────────────────────────────────────────
    seen = set()
    unique = []
    for p in all_raw:
        key = p["name"].lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    print(f"  After dedup: {len(unique)}")

    # ── Filter with Claude ────────────────────────────────────────────────────
    print("\n[3/3] Filtering with Claude AI...")
    if unique:
        filtered = filter_with_claude(unique)
        print(f"  Astroman-relevant products: {len(filtered)}")
    else:
        filtered = []
        print("  No products to filter — scraping may have been blocked")

    # ── Send to Telegram ──────────────────────────────────────────────────────
    print("\n[4/4] Sending to Telegram...")
    message = format_telegram_message(filtered)
    success = send_telegram(message)

    if not success:
        # Last resort: send raw list
        fallback = f"🔭 Product Scout {datetime.now().strftime('%d %b')} — {len(filtered)} products found\n"
        for p in filtered[:5]:
            fallback += f"• {p.get('name','?')} ({p.get('price_usd','?')})\n"
        send_telegram(fallback)

    print(f"\n{'='*50}")
    print("Done.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
