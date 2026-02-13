"""
Product scraper for Chinese wholesale suppliers.
Scrapes Alibaba, 1688.com, and DHgate for trending products.
"""

import httpx
import asyncio
import random
import re
import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional
from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

# ─── Data Model ───────────────────────────────────────────────
@dataclass
class Product:
    name: str
    price: str
    link: str
    source: str  # alibaba | 1688 | dhgate
    category: str
    image_url: str = ""
    min_order: str = ""
    orders_or_reviews: str = ""
    supplier: str = ""

    def to_dict(self):
        return asdict(self)

    def to_telegram_text(self) -> str:
        """Format product for Telegram message."""
        lines = [
            f"🏷 *{_esc(self.name[:80])}*",
            f"💰 {_esc(self.price)}",
        ]
        if self.min_order:
            lines.append(f"📦 MOQ: {_esc(self.min_order)}")
        if self.orders_or_reviews:
            lines.append(f"🔥 {_esc(self.orders_or_reviews)}")
        if self.supplier:
            lines.append(f"🏭 {_esc(self.supplier)}")
        lines.append(f"🔗 [Open on {_esc(self.source)}]({self.link})")
        return "\n".join(lines)


def _esc(text: str) -> str:
    """Escape Telegram MarkdownV2 special chars."""
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


# ─── Rotating User Agents ────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# ─── Category Keywords ────────────────────────────────────────
CATEGORIES = {
    "lamps": ["led lamp", "desk lamp", "night light", "smart lamp", "table lamp", "moon lamp"],
    "telescopes": ["telescope", "astronomical telescope", "monocular telescope", "spotting scope"],
    "binoculars": ["binoculars", "night vision binoculars", "compact binoculars", "hunting binoculars"],
    "kids_toys": ["kids toys", "educational toys", "rc car toy", "building blocks", "plush toy trending"],
    "electronics": ["wireless earbuds", "smart watch", "phone accessories", "portable charger", "led strip"],
}


def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


# ═══════════════════════════════════════════════════════════════
#  ALIBABA SCRAPER
# ═══════════════════════════════════════════════════════════════
async def scrape_alibaba(client: httpx.AsyncClient, keyword: str, category: str, max_items: int = 8) -> list[Product]:
    """Scrape Alibaba search results for a keyword."""
    products = []
    url = "https://www.alibaba.com/trade/search"
    params = {
        "SearchText": keyword,
        "viewtype": "G",  # Gallery view
        "sortType": "TRALV",  # Trade level / best sellers
    }

    try:
        resp = await client.get(url, params=params, headers=_headers(), timeout=20, follow_redirects=True)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        # Method 1: Parse JSON-LD / embedded data
        products.extend(_parse_alibaba_html(tree, category, max_items))

        # Method 2: Try embedded __NEXT_DATA__ or similar JSON blobs
        if not products:
            products.extend(_parse_alibaba_json(resp.text, category, max_items))

    except Exception as e:
        logger.warning(f"Alibaba scrape failed for '{keyword}': {e}")

    return products[:max_items]


def _parse_alibaba_html(tree: HTMLParser, category: str, max_items: int) -> list[Product]:
    """Parse Alibaba product cards from HTML."""
    products = []

    # Alibaba uses various card selectors - try multiple
    selectors = [
        "div.organic-list div.fy23-search-card",
        "div.organic-list div.J-offer-wrapper",
        "div[class*='search-card']",
        "div[class*='offer-wrapper']",
        "div.gallery-offer-list div[class*='card']",
    ]

    cards = []
    for sel in selectors:
        cards = tree.css(sel)
        if cards:
            break

    # Fallback: grab all links that look like product links
    if not cards:
        cards = tree.css("a[href*='/product-detail/']")
        for a_tag in cards[:max_items]:
            href = a_tag.attributes.get("href", "")
            if not href.startswith("http"):
                href = "https:" + href if href.startswith("//") else "https://www.alibaba.com" + href
            name = a_tag.text(strip=True)[:120] or "Alibaba Product"
            products.append(Product(
                name=name, price="See listing", link=href,
                source="Alibaba", category=category,
            ))
        return products[:max_items]

    for card in cards[:max_items]:
        try:
            # Title
            title_el = card.css_first("h2, [class*='title'], [class*='name'], a[title]")
            name = ""
            if title_el:
                name = title_el.attributes.get("title", "") or title_el.text(strip=True)
            name = name[:120] or "Alibaba Product"

            # Link
            link_el = card.css_first("a[href*='alibaba.com'], a[href*='/product-detail/']")
            link = ""
            if link_el:
                link = link_el.attributes.get("href", "")
                if not link.startswith("http"):
                    link = "https:" + link if link.startswith("//") else "https://www.alibaba.com" + link

            # Price
            price_el = card.css_first("[class*='price'], [class*='Price']")
            price = price_el.text(strip=True) if price_el else "See listing"

            # MOQ
            moq_el = card.css_first("[class*='moq'], [class*='MOQ'], [class*='min-order']")
            moq = moq_el.text(strip=True) if moq_el else ""

            # Image
            img_el = card.css_first("img[src], img[data-src]")
            img = ""
            if img_el:
                img = img_el.attributes.get("src", "") or img_el.attributes.get("data-src", "")

            # Supplier
            supplier_el = card.css_first("[class*='company'], [class*='supplier']")
            supplier = supplier_el.text(strip=True) if supplier_el else ""

            if link:
                products.append(Product(
                    name=name, price=price, link=link,
                    source="Alibaba", category=category,
                    image_url=img, min_order=moq, supplier=supplier,
                ))
        except Exception:
            continue

    return products


def _parse_alibaba_json(html: str, category: str, max_items: int) -> list[Product]:
    """Try to extract product data from embedded JSON in page."""
    products = []
    # Look for JSON data blobs in script tags
    patterns = [
        r'window\.__INIT_DATA__\s*=\s*({.+?});',
        r'"offerList"\s*:\s*(\[.+?\])',
        r'"itemList"\s*:\s*(\[.+?\])',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                items = data if isinstance(data, list) else []
                if isinstance(data, dict):
                    # Try to find item arrays in nested structure
                    for key in ["offerList", "itemList", "data", "result"]:
                        if key in data and isinstance(data[key], list):
                            items = data[key]
                            break

                for item in items[:max_items]:
                    if isinstance(item, dict):
                        name = item.get("title", item.get("name", item.get("subject", "")))[:120]
                        price = item.get("price", item.get("priceStr", "See listing"))
                        if isinstance(price, dict):
                            price = price.get("priceStr", str(price.get("min", "")))
                        link = item.get("detailUrl", item.get("href", item.get("productUrl", "")))
                        if link and not link.startswith("http"):
                            link = "https:" + link if link.startswith("//") else "https://www.alibaba.com" + link
                        img = item.get("image", item.get("imgUrl", ""))

                        if name and link:
                            products.append(Product(
                                name=str(name), price=str(price), link=link,
                                source="Alibaba", category=category, image_url=str(img),
                            ))
            except (json.JSONDecodeError, TypeError):
                continue

    return products[:max_items]


# ═══════════════════════════════════════════════════════════════
#  DHGATE SCRAPER (backup supplier source)
# ═══════════════════════════════════════════════════════════════
async def scrape_dhgate(client: httpx.AsyncClient, keyword: str, category: str, max_items: int = 5) -> list[Product]:
    """Scrape DHgate search results."""
    products = []
    url = f"https://www.dhgate.com/wholesale/search.do"
    params = {
        "searchkey": keyword,
        "searchSource": "sort",
        "sortby": "bestmatch#seo",
    }

    try:
        resp = await client.get(url, params=params, headers=_headers(), timeout=20, follow_redirects=True)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        cards = tree.css("div.gallery-item, div[class*='product-item'], div[class*='listitem']")
        if not cards:
            # Try link-based extraction
            links = tree.css("a[href*='/product/']")
            for a_tag in links[:max_items]:
                href = a_tag.attributes.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.dhgate.com" + href
                name = a_tag.attributes.get("title", a_tag.text(strip=True))[:120] or "DHgate Product"
                products.append(Product(
                    name=name, price="See listing", link=href,
                    source="DHgate", category=category,
                ))
            return products[:max_items]

        for card in cards[:max_items]:
            try:
                title_el = card.css_first("a[title], [class*='title'], h3, h4")
                name = ""
                if title_el:
                    name = title_el.attributes.get("title", "") or title_el.text(strip=True)
                name = name[:120] or "DHgate Product"

                link_el = card.css_first("a[href*='dhgate.com'], a[href*='/product/']")
                link = ""
                if link_el:
                    link = link_el.attributes.get("href", "")
                    if not link.startswith("http"):
                        link = "https://www.dhgate.com" + link

                price_el = card.css_first("[class*='price']")
                price = price_el.text(strip=True) if price_el else "See listing"

                review_el = card.css_first("[class*='review'], [class*='order'], [class*='sold']")
                reviews = review_el.text(strip=True) if review_el else ""

                if link:
                    products.append(Product(
                        name=name, price=price, link=link,
                        source="DHgate", category=category,
                        orders_or_reviews=reviews,
                    ))
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"DHgate scrape failed for '{keyword}': {e}")

    return products[:max_items]


# ═══════════════════════════════════════════════════════════════
#  MAIN SCRAPING ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════
async def scrape_all_categories(categories: dict[str, list[str]] | None = None) -> list[Product]:
    """
    Scrape all categories across all supplier sites.
    Returns a flat list of all products found.
    """
    cats = categories or CATEGORIES
    all_products: list[Product] = []

    async with httpx.AsyncClient(
        http2=True,
        follow_redirects=True,
        timeout=25,
    ) as client:
        tasks = []
        for cat_name, keywords in cats.items():
            # Pick 1-2 random keywords per category to avoid hammering
            selected = random.sample(keywords, min(2, len(keywords)))
            for kw in selected:
                tasks.append(scrape_alibaba(client, kw, cat_name))
                tasks.append(scrape_dhgate(client, kw, cat_name))
                # Small delay between task creation
                await asyncio.sleep(random.uniform(0.5, 1.5))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Task failed: {result}")

    # Deduplicate by link
    seen_links = set()
    unique = []
    for p in all_products:
        if p.link not in seen_links:
            seen_links.add(p.link)
            unique.append(p)

    logger.info(f"Scraped {len(unique)} unique products across {len(cats)} categories")
    return unique


def scrape_sync() -> list[Product]:
    """Synchronous wrapper for scrape_all_categories."""
    return asyncio.run(scrape_all_categories())
