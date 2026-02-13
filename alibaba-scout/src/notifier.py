"""
Sends the product digest via Telegram bot with session labels.
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


def send_daily_digest(
    products: list[dict],
    bot_token: str,
    chat_id: str,
    session_label: str = "",
) -> bool:
    """
    Send top products as a formatted Telegram message.
    session_label: e.g. "🌤 შუადღის სელექცია" or "🌙 საღამოს სელექცია"
    """
    if not products:
        _send_message(bot_token, chat_id, "⚠️ No products found this session\\. Will try next time\\!")
        return False

    date_str = datetime.now().strftime("%d/%m/%Y")
    time_str = datetime.now().strftime("%H:%M")
    count = len(products)

    # ── Build header ──────────────────────────────────────────
    label = session_label or "🔥 Product Scout"
    header = (
        f"*{_esc(label)}*\n"
        f"📅 {_esc(date_str)}  ⏰ {_esc(time_str)}\n"
        f"📦 Top {count} viral products\n"
        f"{'─' * 28}\n\n"
    )

    current_msg = header

    # ── Build product entries ─────────────────────────────────
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

        # Telegram max 4096 chars — split if needed
        if len(current_msg) + len(entry) > 3800:
            _send_message(bot_token, chat_id, current_msg)
            current_msg = entry
        else:
            current_msg += entry

    # ── Footer ────────────────────────────────────────────────
    next_session = "18:00" if "შუადღ" in (session_label or "") else "12:00"
    footer = (
        f"{'─' * 28}\n"
        f"⏭ შემდეგი: {_esc(next_session)}\n"
        f"🤖 _Alibaba Scout Bot_"
    )
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
