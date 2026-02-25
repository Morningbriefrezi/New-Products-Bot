"""
Sends the structured product digest via Telegram.
3 sections: Viral / Astroman / Bestsellers
"""

import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}"

SESSION_LABELS = {
    "noon": "🌤 შუადღის სელექცია",
    "evening": "🌙 საღამოს სელექცია",
}

SECTIONS = [
    ("viral",       "🔥 VIRAL — TikTok პოტენციალი",        3),
    ("astroman",    "🔭 ASTROMAN — მაღაზიისთვის",           5),
    ("bestsellers", "🏆 BESTSELLERS — დამტკიცებული გაყიდვა", 2),
]


def _esc(text):
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def send_daily_digest(ranked, bot_token, chat_id, session_label=""):
    """
    ranked: dict with keys viral, astroman, bestsellers — each a list of product dicts.
    """
    total = sum(len(v) for v in ranked.values())
    if total == 0:
        _send_message(bot_token, chat_id, "⚠️ No products found this session\\. Will try next time\\!")
        return False

    date_str = datetime.now().strftime("%d/%m/%Y")
    time_str = datetime.now().strftime("%H:%M")
    label = SESSION_LABELS.get(session_label, session_label or "📦 Product Scout")

    header = (
        f"*{_esc(label)}*\n"
        f"📅 {_esc(date_str)}  ⏰ {_esc(time_str)}\n"
        f"{'─' * 30}\n\n"
    )

    messages = [header]
    current = header

    for section_key, section_title, expected_count in SECTIONS:
        products = ranked.get(section_key, [])
        if not products:
            continue

        section_header = f"*{_esc(section_title)}* \\({len(products)}\\)\n\n"

        if len(current) + len(section_header) > 3800:
            messages.append(current)
            current = section_header
        else:
            current += section_header

        for i, product in enumerate(products, 1):
            name = product.get("name", "Unknown")[:80]
            price = product.get("price", "N/A")
            link = product.get("link", "#")
            source = product.get("source", "Unknown")
            score = product.get("score", 0)
            reason = product.get("reason", "")
            min_order = product.get("min_order", "")
            orders = product.get("orders_or_reviews", "")
            supplier = product.get("supplier", "")

            entry = f"*{i}\\. {_esc(name)}*\n"
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

            if len(current) + len(entry) > 3800:
                messages.append(current)
                current = entry
            else:
                current += entry

        current += f"{'─' * 30}\n\n"

    next_session = "18:00" if session_label == "noon" else "12:00"
    footer = f"⏭ შემდეგი: {_esc(next_session)}\n🤖 _Astroman Product Scout_"
    current += footer
    messages.append(current)

    # Deduplicate (header may appear twice if nothing was added after it)
    seen = set()
    success = True
    for msg in messages:
        if msg in seen or msg == header:
            continue
        seen.add(msg)
        if not _send_message(bot_token, chat_id, msg):
            success = False

    return success


def _send_message(bot_token, chat_id, text):
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
            # Retry without markdown
            payload["parse_mode"] = "HTML"
            payload["text"] = text.replace("\\", "")
            resp2 = httpx.post(url, json=payload, timeout=15)
            return resp2.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_error_alert(error_msg, bot_token, chat_id):
    text = f"⚠️ *Astroman Scout Error*\n\n{_esc(error_msg)}"
    return _send_message(bot_token, chat_id, text)
