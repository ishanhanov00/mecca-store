"""
Первичное заполнение БД: системные категории раздела «Меню» (создаются один
раз, если таблица категорий пуста) + одна стартовая категория садака, чтобы
магазин не выглядел пустым при первом запуске. Администратор может свободно
менять/добавлять/скрывать категории позже через админ-панель.
"""
from sqlalchemy.orm import Session

from app import models

SYSTEM_MENU_CATEGORIES = [
    {"key": "our_set", "icon": "⭐", "names": {
        "ru": "Наш сет", "uz": "Bizning to'plam", "ar": "طقم الوجبات", "en": "Our Set"}},
    {"key": "breakfast", "icon": "🍳", "names": {
        "ru": "Завтрак", "uz": "Nonushta", "ar": "الإفطار", "en": "Breakfast"}},
    {"key": "first_courses", "icon": "🍲", "names": {
        "ru": "Первые блюда", "uz": "Birinchi taomlar", "ar": "الأطباق الأولى", "en": "Soups"}},
    {"key": "main_courses", "icon": "🍛", "names": {
        "ru": "Вторые блюда", "uz": "Ikkinchi taomlar", "ar": "الأطباق الرئيسية", "en": "Main Courses"}},
    {"key": "salads", "icon": "🥗", "names": {
        "ru": "Салаты", "uz": "Salatlar", "ar": "السلطات", "en": "Salads"}},
    {"key": "drinks", "icon": "🥤", "names": {
        "ru": "Напитки", "uz": "Ichimliklar", "ar": "المشروبات", "en": "Drinks"}},
]

DEFAULT_SADAKA_CATEGORY = {
    "key": "sadaka_food", "icon": "🍱", "names": {
        "ru": "Садака едой", "uz": "Sadaqa taom bilan", "ar": "صدقة بالطعام", "en": "Sadaqah — Food"}}


def run_seed(db: Session) -> None:
    if db.query(models.Category).count() > 0:
        return  # уже заполнено — ничего не делаем, чтобы не затирать правки админа

    for i, cat in enumerate(SYSTEM_MENU_CATEGORIES):
        db.add(models.Category(
            key=cat["key"], section=models.Section.menu, names=cat["names"],
            icon=cat["icon"], sort_order=i, is_active=True, is_system=True,
        ))

    db.add(models.Category(
        key=DEFAULT_SADAKA_CATEGORY["key"], section=models.Section.sadaka,
        names=DEFAULT_SADAKA_CATEGORY["names"], icon=DEFAULT_SADAKA_CATEGORY["icon"],
        sort_order=0, is_active=True, is_system=False,
    ))

    db.commit()