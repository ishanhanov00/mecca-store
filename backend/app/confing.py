"""
Конфигурация приложения. Все настройки читаются из переменных окружения (.env).
Ничего секретного не хранится в коде.
"""
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Корень проекта (на 3 уровня выше этого файла: backend/app/config.py -> project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Ищем .env в корне проекта
load_dotenv(BASE_DIR / ".env")


def _parse_admin_ids(raw: str) -> List[int]:
    ids = []
    for part in raw.replace(" ", "").split(","):
        if part.strip().lstrip("-").isdigit():
            ids.append(int(part))
    return ids


class Settings:
    # --- Telegram ---
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "http://localhost:8000").rstrip("/")
    ADMIN_WEBAPP_URL: str = os.getenv("ADMIN_WEBAPP_URL", "").rstrip("/") or None

    # --- Security ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-please-in-env")
    # Если True, initData не проверяется по HMAC (ТОЛЬКО для локальной разработки без Telegram!)
    DEV_SKIP_TELEGRAM_AUTH: bool = os.getenv("DEV_SKIP_TELEGRAM_AUTH", "false").lower() == "true"
    # Сколько секунд считать initData валидным (защита от replay). 0 = не проверять.
    INIT_DATA_MAX_AGE: int = int(os.getenv("INIT_DATA_MAX_AGE", "86400"))

    # --- Database ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'database' / 'shop.db').as_posix()}"
    )

    # --- Business defaults (используются только при первом запуске / если Settings пуст) ---
    BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "Mecca Shop")
    CURRENCY: str = os.getenv("CURRENCY", "SAR")
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "ru")

    # --- Files ---
    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "8"))

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: List[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]


settings = Settings()

settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(settings.UPLOADS_DIR / "products").mkdir(parents=True, exist_ok=True)
(settings.UPLOADS_DIR / "receipts").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "database").mkdir(parents=True, exist_ok=True)