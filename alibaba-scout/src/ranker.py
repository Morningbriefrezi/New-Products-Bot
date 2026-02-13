"""
Uses OpenAI to rank scraped products by viral / resale potential.
Returns the top 10 most promising products.
"""

import json
import logging
from openai import OpenAI

from .scraper import Product

logger = logging.getLogger(__name__)

RANKING_PROMPT = """You are an expert e-commerce product analyst specializing in dropshipping and resale businesses.

I will give you a list of products scraped from Chinese wholesale suppliers (Alibaba, DHgate, 1688).
Your job is to rank them by VIRAL & RESALE POTENTIAL and return the TOP 10.

Scoring criteria (weight each equally):
1. **Trend potential** – Is this product trending on TikTok/Instagram/Amazon? Is it a novelty item?
2. **Profit margin** – Low wholesale price + high perceived value = good margin.
3. **Broad appeal** – Would many people want this? Gift-worthy? Impulse buy?
4. **Low competition signal** – Unique or niche enough to stand out.
5. **Shippability** – Small, light, not fragile = easier to sell online.

IMPORTANT RULES:
- Return EXACTLY 10 products (or fewer if less than 10 were provided).
- Return ONLY valid JSON — no markdown, no explanation, no preamble.
- Preserve the original product data exactly (name, price, link, source, category).
- Add a "score" field (1-100) and a "reason" field (1 sentence why it's viral).

Return format:
[
  {
    "name": "...",
    "price": "...",
    "link": "...",
    "source": "...",
    "category": "...",
    "image_url": "...",
    "min_order": "...",
    "orders_or_reviews": "...",
    "supplier": "...",
    "score": 85,
    "reason": "Trending on TikTok, high perceived value, great margins."
  }
]
"""


def rank_products(products: list[Product], api_key: str, model: str = "gpt-4o-mini") -> list[dict]:
    """
    Send products to OpenAI for viral potential ranking.
    Returns top 10 as list of dicts with added 'score' and 'reason' fields.
    """
    if not products:
        logger.warning("No products to rank")
        return []

    # Prepare product data for the prompt
    product_data = [p.to_dict() for p in products]
    product_json = json.dumps(product_data, ensure_ascii=False, indent=2)

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": RANKING_PROMPT},
                {"role": "user", "content": f"Here are {len(products)} products to rank:\n\n{product_json}"},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"}  # Force JSON output
        )

        raw = response.choices[0].message.content.strip()

        # Parse response
        parsed = json.loads(raw)

        # Handle both {"products": [...]} and [...] formats
        if isinstance(parsed, dict):
            for key in ["products", "top_products", "results", "items"]:
                if key in parsed:
                    parsed = parsed[key]
                    break
            else:
                # If it's a dict but no known key, try first list value
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break

        if not isinstance(parsed, list):
            logger.error(f"Unexpected OpenAI response format: {type(parsed)}")
            return []

        # Sort by score descending
        parsed.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(f"OpenAI ranked {len(parsed)} products")
        return parsed[:10]

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON response: {e}")
        logger.debug(f"Raw response: {raw}")
        return []
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        return []


def rank_products_fallback(products: list[Product]) -> list[dict]:
    """
    Fallback ranking without OpenAI — rank by price info availability
    and category diversity. Used when API key is missing or call fails.
    """
    scored = []
    for p in products:
        score = 50  # base
        if p.price and p.price != "See listing":
            score += 15
        if p.orders_or_reviews:
            score += 20
        if p.image_url:
            score += 5
        if p.min_order:
            score += 5
        if p.supplier:
            score += 5
        scored.append({**p.to_dict(), "score": score, "reason": "Auto-scored (no AI)"})

    # Sort and ensure category diversity
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Pick top items while maintaining category spread
    seen_cats: dict[str, int] = {}
    diverse: list[dict] = []
    for item in scored:
        cat = item["category"]
        if seen_cats.get(cat, 0) < 3:  # max 3 per category
            diverse.append(item)
            seen_cats[cat] = seen_cats.get(cat, 0) + 1
        if len(diverse) >= 10:
            break

    return diverse
