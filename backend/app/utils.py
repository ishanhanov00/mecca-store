"""
Вспомогательные функции: выбор перевода, работа с настройками,
отправка уведомлений в Telegram напрямую через Bot API (без aiogram —
это отдельный процесс, backend просто дёргает HTTP API Telegram).
"""
import random
import string
from datetime import datetime, time as dtime
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app import models

SUPPORTED_LANGUAGES = ["ru", "uz", "ar", "en"]

DEFAULT_SETTINGS: Dict[str, str] = {
    "business_name": settings.BUSINESS_NAME,
    "logo_url": "",
    "description": "",
    "phone": "",
    "whatsapp": "",
    "instagram": "",
    "address": "Мекка, Саудовская Аравия",
    "work_open": "08:00",
    "work_close": "23:00",
    "is_open_override": "auto",  # auto | open | closed
    "allow_orders_outside_hours": "true",
    "pickup_enabled": "true",
    "bank_name": "",
    "bank_recipient": "",
    "bank_iban": "",
    "bank_account": "",
    "bank_extra": "",
    "welcome_text": "Добро пожаловать! Свежая еда и садака в Мекке 🤲",
    "default_language": settings.DEFAULT_LANGUAGE,
    "currency": settings.CURRENCY,
}


def pick_lang(data: Optional[Dict[str, Any]], lang: str, fallback: str = "ru") -> str:
    """Выбирает перевод из JSON-словаря {"ru": ..., "en": ...} с fallback на основной язык."""
    if not data:
        return ""
    if data.get(lang):
        return data[lang]
    if data.get(fallback):
        return data[fallback]
    for v in data.values():
        if v:
            return v
    return ""


def generate_order_number(db: Session) -> str:
    """Генерирует короткий уникальный номер заказа вида A1024."""
    for _ in range(10):
        candidate = "".join(random.choices(string.digits, k=6))
        exists = db.query(models.Order.id).filter(models.Order.order_number == candidate).first()
        if not exists:
            return candidate
    # Крайне маловероятный фолбэк
    return datetime.utcnow().strftime("%y%m%d%H%M%S")


def get_settings_dict(db: Session) -> Dict[str, str]:
    rows = db.query(models.Settings).all()
    result = dict(DEFAULT_SETTINGS)
    for row in rows:
        result[row.key] = row.value
    return result


def set_settings(db: Session, values: Dict[str, Any]) -> None:
    for key, value in values.items():
        if value is None:
            continue
        row = db.query(models.Settings).filter(models.Settings.key == key).first()
        str_value = str(value) if not isinstance(value, bool) else ("true" if value else "false")
        if row:
            row.value = str_value
        else:
            db.add(models.Settings(key=key, value=str_value))
    db.commit()


def is_shop_open(settings_dict: Dict[str, str]) -> bool:
    override = settings_dict.get("is_open_override", "auto")
    if override == "open":
        return True
    if override == "closed":
        return False
    try:
        open_t = dtime.fromisoformat(settings_dict.get("work_open") or "00:00")
        close_t = dtime.fromisoformat(settings_dict.get("work_close") or "23:59")
    except ValueError:
        return True
    now_t = datetime.now().time()
    if open_t <= close_t:
        return open_t <= now_t <= close_t
    # Ночной интервал, например 20:00 - 02:00
    return now_t >= open_t or now_t <= close_t


async def send_telegram_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> bool:
    """Отправляет сообщение через Telegram Bot API напрямую (без aiogram)."""
    if not settings.BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False


async def send_telegram_photo(chat_id: int, photo_path: str, caption: str = "") -> bool:
    if not settings.BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendPhoto"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
                resp = await client.post(url, data=data, files=files)
                return resp.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


async def notify_admins_new_order(order: models.Order) -> None:
    if not settings.ADMIN_IDS:
        return
    lines = [f"🔔 <b>НОВЫЙ ЗАКАЗ №{order.order_number}</b>", ""]
    lines.append(f"👤 Клиент: {order.customer_name}")
    lines.append(f"📞 Телефон: {order.phone}")
    if order.username:
        lines.append(f"🔗 @{order.username}")
    if order.address:
        lines.append(f"📍 {order.address}")
    lines.append("")
    for item in order.items:
        lines.append(f"• {item.product_name} × {item.quantity} — {item.subtotal} {order.currency}")
    lines.append("")
    lines.append(f"💰 Итого: {order.total} {order.currency}")
    if order.payment_method == models.PaymentMethod.cash:
        lines.append("💵 Оплата: наличными")
    else:
        lines.append("🏦 Оплата: банковский перевод")
        if order.receipt_path:
            lines.append("📎 Чек прикреплён")
        else:
            lines.append("⏳ Чек ещё не загружен")
    if order.comment:
        lines.append(f"💬 Комментарий: {order.comment}")

    text = "\n".join(lines)
    for admin_id in settings.ADMIN_IDS:
        await send_telegram_message(admin_id, text)


async def notify_customer_status_change(order: models.Order, message: str) -> None:
    if order.telegram_id:
        await send_telegram_message(order.telegram_id, message)


def decimal_to_float(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return value