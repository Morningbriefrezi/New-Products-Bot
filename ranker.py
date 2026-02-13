"""
Uses OpenAI to rank scraped products by viral / resale potential.
"""

import json
import logging
from openai import OpenAI

from scraper import Product

logger = logging.getLogger(__name__)

RANKING_PROMPT = """You are an expert e-commerce product analyst specializing in dropshipping and resale businesses.

I will give you a list of products scraped from Chinese wholesale suppliers (Alibaba, DHgate, 1688).
Your job is to rank them by VIRAL & RESALE POTENTIAL and return the TOP {top_n}.

Scoring criteria (weight each equally):
1. **Trend potential** – Is this product trending on TikTok/Instagram/Amazon? Is it a novelty item?
2. **Profit margin** – Low wholesale price + high perceived value = good margin.
3. **Broad appeal** – Would many people want this? Gift-worthy? Impulse buy?
4. **Low competition signal** – Unique or niche enough to stand out.
5. **Shippability** – Small, light, not fragile = easier to sell online.

IMPORTANT RULES:
- Return EXACTLY {top_n} products (or fewer if less than {top_n} were provided).
- Return ONLY valid JSON — no markdown, no explanation, no preamble.
- Preserve the original product data exactly (name, price, link, source, category).
- Add a "score" field (1-100) and a "reason" field (1 sentence why it's viral).

Return format:
[
  {{
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
  }}
]
"""


def rank_products(products, api_key, model="gpt-4o-mini", top_n=5):
    if not products:
        logger.warning("No products to rank")
        return []

    product_data = [p.to_dict() for p in products]
    product_json = json.dumps(product_data, ensure_ascii=False, indent=2)

    prompt = RANKING_PROMPT.format(top_n=top_n)
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Here are {len(products)} products to rank:\n\n{product_json}"},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        if isinstance(parsed, dict):
            for key in ["products", "top_products", "results", "items"]:
                if key in parsed:
                    parsed = parsed[key]
                    break
            else:
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break

        if not isinstance(parsed, list):
            logger.error(f"Unexpected OpenAI response format: {type(parsed)}")
            return []

        parsed.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"OpenAI ranked {len(parsed)} products, returning top {top_n}")
        return parsed[:top_n]

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON response: {e}")
        return []
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        return []


def rank_products_fallback(products, top_n=5):
    scored = []
    for p in products:
        score = 50
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

    scored.sort(key=lambda x: x["score"], reverse=True)

    seen_cats = {}
    diverse = []
    max_per_cat = max(1, (top_n // len(set(p.category for p in products)) + 1)) if products else 2

    for item in scored:
        cat = item["category"]
        if seen_cats.get(cat, 0) < max_per_cat:
            diverse.append(item)
            seen_cats[cat] = seen_cats.get(cat, 0) + 1
        if len(diverse) >= top_n:
            break

    return diverse
