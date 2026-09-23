"""
Проверка Telegram WebApp initData на сервере.

Клиент присылает initData (строку) в заголовке X-Telegram-Init-Data.
Мы проверяем подпись HMAC-SHA256 по алгоритму, описанному в документации
Telegram: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

НИКОГДА не доверяем данным пользователя (telegram_id, username и т.д.),
которые пришли в теле запроса — только тем, что мы сами извлекли из
проверенной initData.
"""
import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models


class TelegramUser:
    def __init__(self, telegram_id: int, username: Optional[str], first_name: Optional[str],
                 last_name: Optional[str], language_code: Optional[str]):
        self.telegram_id = telegram_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.language_code = language_code

    @property
    def is_admin(self) -> bool:
        return self.telegram_id in settings.ADMIN_IDS


def _validate_init_data(init_data: str) -> dict:
    """Проверяет подпись initData и возвращает распарсенные поля.
    Бросает HTTPException(401), если подпись неверна или истёк срок."""
    if not init_data:
        raise HTTPException(status_code=401, detail="Отсутствует initData Telegram")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="initData без подписи")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="Неверная подпись initData")

    if settings.INIT_DATA_MAX_AGE:
        auth_date = int(parsed.get("auth_date", "0"))
        if auth_date and (time.time() - auth_date) > settings.INIT_DATA_MAX_AGE:
            raise HTTPException(status_code=401, detail="initData устарела, откройте магазин заново")

    return parsed


def get_current_telegram_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
) -> TelegramUser:
    """FastAPI-зависимость: проверяет initData и возвращает данные пользователя Telegram.

    В DEV_SKIP_TELEGRAM_AUTH=true режиме (только для локальной разработки вне Telegram)
    допускает передачу telegram_id напрямую через заголовок X-Debug-Telegram-Id.
    """
    if settings.DEV_SKIP_TELEGRAM_AUTH:
        # Только для разработки! В проде обязательно выставьте DEV_SKIP_TELEGRAM_AUTH=false
        return TelegramUser(telegram_id=99999999, username="dev_user", first_name="Dev",
                             last_name=None, language_code="ru")

    if not settings.BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN не настроен на сервере")

    parsed = _validate_init_data(x_telegram_init_data or "")

    user_json = parsed.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="initData без данных пользователя")

    try:
        user_obj = json.loads(user_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Некорректные данные пользователя")

    return TelegramUser(
        telegram_id=user_obj.get("id"),
        username=user_obj.get("username"),
        first_name=user_obj.get("first_name"),
        last_name=user_obj.get("last_name"),
        language_code=user_obj.get("language_code"),
    )


def require_admin(user: TelegramUser = Depends(get_current_telegram_user)) -> TelegramUser:
    """Зависимость для эндпоинтов админки — доступ только Telegram ID из ADMIN_IDS."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ только для администратора")
    return user


def get_or_create_user(db: Session, tg_user: TelegramUser) -> models.User:
    user = db.query(models.User).filter(models.User.telegram_id == tg_user.telegram_id).first()
    if user is None:
        user = models.User(
            telegram_id=tg_user.telegram_id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language=tg_user.language_code if tg_user.language_code in ("ru", "uz", "ar", "en") else "ru",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        changed = False
        if user.username != tg_user.username:
            user.username = tg_user.username
            changed = True
        if user.first_name != tg_user.first_name:
            user.first_name = tg_user.first_name
            changed = True
        if changed:
            db.commit()
    return user