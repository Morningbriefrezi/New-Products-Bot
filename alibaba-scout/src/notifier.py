"""
Sends the daily top-10 product digest via Telegram bot.
"""

import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def send_daily_digest(products: list[dict], bot_token: str, chat_id: str) -> bool:
    """
    Send top-10 products as a formatted Telegram message.
    Splits into multiple messages if too long.
    """
    if not products:
        _send_message(bot_token, chat_id, "⚠️ No products found today\\. Will try again tomorrow\\!")
        return False

    date_str = datetime.now().strftime("%d/%m/%Y")

    header = (
        f"🔥 *Daily Viral Products Scout* 🔥\n"
        f"📅 {_esc(date_str)}\n"
        f"{'─' * 30}\n\n"
    )

    messages = [header]
    current_msg = header

    for i, product in enumerate(products, 1):
        name = product.get("name", "Unknown")[:80]
        price = product.get("price", "N/A")
        link = product.get("link", "#")
        source = product.get("source", "Unknown")
        category = product.get("category", "")
        score = product.get("score", 0)
        reason = product.get("reason", "")
        min_order = product.get("min_order", "")
        orders = product.get("orders_or_reviews", "")
        supplier = product.get("supplier", "")

        # Category emoji
        cat_emoji = {
            "lamps": "💡", "telescopes": "🔭", "binoculars": "🔭",
            "kids_toys": "🧸", "electronics": "📱",
        }.get(category, "📦")

        entry = f"{cat_emoji} *{i}\\. {_esc(name)}*\n"
        entry += f"💰 {_esc(price)}\n"
        if min_order:
            entry += f"📦 MOQ: {_esc(min_order)}\n"
        if orders:
            entry += f"🔥 {_esc(orders)}\n"
        if supplier:
            entry += f"🏭 {_esc(supplier)}\n"
        entry += f"⭐ Score: {score}/100\n"
        if reason:
            entry += f"💡 {_esc(reason)}\n"
        entry += f"🔗 [Open on {_esc(source)}]({link})\n\n"

        # Telegram has 4096 char limit per message
        if len(current_msg) + len(entry) > 3800:
            _send_message(bot_token, chat_id, current_msg)
            current_msg = entry
        else:
            current_msg += entry

    # Send remaining
    footer = f"{'─' * 30}\n🤖 _Powered by Alibaba Scout Bot_"
    current_msg += footer
    success = _send_message(bot_token, chat_id, current_msg)

    return success


def _send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a single Telegram message."""
    url = f"{TELEGRAM_API.format(token=bot_token)}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }

    try:
        resp = httpx.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            logger.info("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
            # Retry without markdown if formatting fails
            payload["parse_mode"] = "HTML"
            payload["text"] = text.replace("\\", "")
            resp2 = httpx.post(url, json=payload, timeout=15)
            return resp2.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_error_alert(error_msg: str, bot_token: str, chat_id: str) -> bool:
    """Send an error notification."""
    text = f"⚠️ *Alibaba Scout Error*\n\n{_esc(error_msg)}"
    return _send_message(bot_token, chat_id, text)
