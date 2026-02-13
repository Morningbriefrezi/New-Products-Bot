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
from dataclasses import dataclass, asdict
from typing import Optional
from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

@dataclass
class Product:
    name: str
    price: str
    link: str
    source: str
    category: str
    image_url: str = ""
    min_order: str = ""
    orders_or_reviews: str = ""
    supplier: str = ""

    def to_dict(self):
        return asdict(self)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

CATEGORIES = {
    "lamps": ["led lamp", "desk lamp", "night light", "smart lamp", "table lamp", "moon lamp"],
    "telescopes": ["telescope", "astronomical telescope", "monocular telescope", "spotting scope"],
    "binoculars": ["binoculars", "night vision binoculars", "compact binoculars", "hunting binoculars"],
    "kids_toys": ["kids toys", "educational toys", "rc car toy", "building blocks", "plush toy trending"],
    "electronics": ["wireless earbuds", "smart watch", "phone accessories", "portable charger", "led strip"],
}


def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


async def scrape_alibaba(client, keyword, category, max_items=8):
    products = []
    url = "https://www.alibaba.com/trade/search"
    params = {"SearchText": keyword, "viewtype": "G", "sortType": "TRALV"}

    try:
        resp = await client.get(url, params=params, headers=_headers(), timeout=20, follow_redirects=True)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)
        products.extend(_parse_alibaba_html(tree, category, max_items))
        if not products:
            products.extend(_parse_alibaba_json(resp.text, category, max_items))
    except Exception as e:
        logger.warning(f"Alibaba scrape failed for '{keyword}': {e}")

    return products[:max_items]


def _parse_alibaba_html(tree, category, max_items):
    products = []
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

    if not cards:
        cards = tree.css("a[href*='/product-detail/']")
        for a_tag in cards[:max_items]:
            href = a_tag.attributes.get("href", "")
            if not href.startswith("http"):
                href = "https:" + href if href.startswith("//") else "https://www.alibaba.com" + href
            name = a_tag.text(strip=True)[:120] or "Alibaba Product"
            products.append(Product(name=name, price="See listing", link=href, source="Alibaba", category=category))
        return products[:max_items]

    for card in cards[:max_items]:
        try:
            title_el = card.css_first("h2, [class*='title'], [class*='name'], a[title]")
            name = ""
            if title_el:
                name = title_el.attributes.get("title", "") or title_el.text(strip=True)
            name = name[:120] or "Alibaba Product"

            link_el = card.css_first("a[href*='alibaba.com'], a[href*='/product-detail/']")
            link = ""
            if link_el:
                link = link_el.attributes.get("href", "")
                if not link.startswith("http"):
                    link = "https:" + link if link.startswith("//") else "https://www.alibaba.com" + link

            price_el = card.css_first("[class*='price'], [class*='Price']")
            price = price_el.text(strip=True) if price_el else "See listing"

            moq_el = card.css_first("[class*='moq'], [class*='MOQ'], [class*='min-order']")
            moq = moq_el.text(strip=True) if moq_el else ""

            img_el = card.css_first("img[src], img[data-src]")
            img = ""
            if img_el:
                img = img_el.attributes.get("src", "") or img_el.attributes.get("data-src", "")

            supplier_el = card.css_first("[class*='company'], [class*='supplier']")
            supplier = supplier_el.text(strip=True) if supplier_el else ""

            if link:
                products.append(Product(
                    name=name, price=price, link=link, source="Alibaba", category=category,
                    image_url=img, min_order=moq, supplier=supplier,
                ))
        except Exception:
            continue

    return products


def _parse_alibaba_json(html, category, max_items):
    products = []
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


async def scrape_dhgate(client, keyword, category, max_items=5):
    products = []
    url = "https://www.dhgate.com/wholesale/search.do"
    params = {"searchkey": keyword, "searchSource": "sort", "sortby": "bestmatch#seo"}

    try:
        resp = await client.get(url, params=params, headers=_headers(), timeout=20, follow_redirects=True)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        cards = tree.css("div.gallery-item, div[class*='product-item'], div[class*='listitem']")
        if not cards:
            links = tree.css("a[href*='/product/']")
            for a_tag in links[:max_items]:
                href = a_tag.attributes.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.dhgate.com" + href
                name = a_tag.attributes.get("title", a_tag.text(strip=True))[:120] or "DHgate Product"
                products.append(Product(name=name, price="See listing", link=href, source="DHgate", category=category))
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
                        name=name, price=price, link=link, source="DHgate",
                        category=category, orders_or_reviews=reviews,
                    ))
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"DHgate scrape failed for '{keyword}': {e}")

    return products[:max_items]


async def scrape_all_categories(categories=None):
    cats = categories or CATEGORIES
    all_products = []

    async with httpx.AsyncClient(http2=True, follow_redirects=True, timeout=25) as client:
        tasks = []
        for cat_name, keywords in cats.items():
            selected = random.sample(keywords, min(2, len(keywords)))
            for kw in selected:
                tasks.append(scrape_alibaba(client, kw, cat_name))
                tasks.append(scrape_dhgate(client, kw, cat_name))
                await asyncio.sleep(random.uniform(0.5, 1.5))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_products.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Task failed: {result}")

    seen_links = set()
    unique = []
    for p in all_products:
        if p.link not in seen_links:
            seen_links.add(p.link)
            unique.append(p)

    logger.info(f"Scraped {len(unique)} unique products across {len(cats)} categories")
    return unique


def scrape_sync():
    return asyncio.run(scrape_all_categories())
