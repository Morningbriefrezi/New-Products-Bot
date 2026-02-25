"""
Uses OpenAI to rank scraped products into 3 sections:
- 3 Viral products (TikTok/social media potential)
- 5 Astroman products (astronomy/space shop relevant)
- 2 Bestsellers (highest proven demand)
"""

import json
import logging
from openai import OpenAI

from scraper import Product

logger = logging.getLogger(__name__)

RANKING_PROMPT = """You are a product analyst for Astroman — a Georgian astronomy and space-themed retail shop.

You will receive a list of products scraped from Alibaba and DHgate.
Your job is to select the best products and split them into exactly 3 sections.

━━━ SECTION 1: VIRAL (pick exactly 3) ━━━
Products with the highest TikTok / Instagram / social media viral potential.
Criteria: visually striking, novelty factor, impulse buy, great for video content, trending aesthetic.
These don't have to be astronomy products — just highly giftable and viral.

━━━ SECTION 2: ASTROMAN (pick exactly 5) ━━━
Products directly suitable for Astroman's shop.
Must relate to: telescopes, space projectors, moon/planet/galaxy lamps, space-themed toys,
constellation/star map items, astronaut decor, STEM astronomy kits, crystal ball lights,
levitating planet lamps — anything an astronomy store would proudly sell.
Pick the most unique and profitable ones with good margin potential.

━━━ SECTION 3: BESTSELLERS (pick exactly 2) ━━━
Products with the highest PROVEN demand — look at orders_or_reviews field.
Highest order count or review count = most proven seller.
These are safe bets with existing market demand.

RULES:
- A product can only appear in ONE section.
- Return ONLY valid JSON — no markdown, no explanation.
- Each product must keep its original fields (name, price, link, source, category, image_url, min_order, orders_or_reviews, supplier).
- Add "score" (1-100) and "reason" (1 short sentence about why it fits this section).

Return format:
{
  "viral": [
    {"name": "...", "price": "...", "link": "...", "source": "...", "category": "...",
     "image_url": "...", "min_order": "...", "orders_or_reviews": "...", "supplier": "...",
     "score": 88, "reason": "Visually stunning, perfect TikTok content, impulse buy."}
  ],
  "astroman": [...5 products...],
  "bestsellers": [...2 products...]
}
"""


def rank_products_structured(products, api_key, model="gpt-4o-mini"):
    """Returns dict with keys: viral (3), astroman (5), bestsellers (2)."""
    if not products:
        logger.warning("No products to rank")
        return {"viral": [], "astroman": [], "bestsellers": []}

    product_data = [p.to_dict() for p in products]
    product_json = json.dumps(product_data, ensure_ascii=False, indent=2)

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": RANKING_PROMPT},
                {"role": "user", "content": f"Here are {len(products)} scraped products. Select the best for each section:\n\n{product_json}"},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        result = {
            "viral": parsed.get("viral", [])[:3],
            "astroman": parsed.get("astroman", [])[:5],
            "bestsellers": parsed.get("bestsellers", [])[:2],
        }

        logger.info(
            f"AI ranked: {len(result['viral'])} viral, "
            f"{len(result['astroman'])} astroman, "
            f"{len(result['bestsellers'])} bestsellers"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON: {e}")
        return {"viral": [], "astroman": [], "bestsellers": []}
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        return {"viral": [], "astroman": [], "bestsellers": []}


def rank_products_fallback(products):
    """Fallback when no OpenAI key — scores by available data signals."""
    def score(p):
        s = 50
        if p.price and p.price != "See listing":
            s += 15
        if p.orders_or_reviews:
            s += 20
        if p.image_url:
            s += 5
        if p.min_order:
            s += 5
        if p.supplier:
            s += 5
        return s

    scored = sorted(
        [{**p.to_dict(), "score": score(p), "reason": "Auto-scored (no AI)"} for p in products],
        key=lambda x: x["score"],
        reverse=True,
    )

    astroman_cats = {"telescopes", "projectors", "space_lamps", "space_toys", "space_decor", "binoculars"}
    astroman = [p for p in scored if p["category"] in astroman_cats][:5]
    used = {p["link"] for p in astroman}

    # Bestsellers: highest orders_or_reviews
    by_orders = sorted(
        [p for p in scored if p["link"] not in used and p["orders_or_reviews"]],
        key=lambda x: x["orders_or_reviews"],
        reverse=True,
    )
    bestsellers = by_orders[:2]
    used.update(p["link"] for p in bestsellers)

    viral = [p for p in scored if p["link"] not in used][:3]

    return {"viral": viral, "astroman": astroman, "bestsellers": bestsellers}
