"""
Pydantic-схемы для запросов/ответов API.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# ---------- Общие ----------

LangDict = Dict[str, str]


class OkResponse(BaseModel):
    ok: bool = True
    message: Optional[str] = None


# ---------- Категории ----------

class CategoryOut(BaseModel):
    id: int
    key: str
    section: str
    names: LangDict
    icon: Optional[str] = None
    sort_order: int
    is_active: bool
    is_system: bool

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    key: str
    section: str
    names: LangDict
    icon: Optional[str] = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    names: Optional[LangDict] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# ---------- Товары ----------

class ProductOut(BaseModel):
    id: int
    category_id: int
    category_key: Optional[str] = None
    section: str
    name: str               # уже переведённое название под текущий язык клиента
    description: Optional[str] = None
    names: Optional[LangDict] = None         # полный словарь (для админки)
    descriptions: Optional[LangDict] = None  # полный словарь (для админки)
    price: Decimal
    currency: str
    quantity: int
    low_stock_threshold: int
    min_order_qty: int
    max_order_qty: Optional[int] = None
    status: str
    image_url: Optional[str] = None
    sort_order: int

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    category_id: int
    section: str
    names: LangDict
    descriptions: Optional[LangDict] = {}
    price: Decimal
    currency: str = "SAR"
    quantity: int = 0
    low_stock_threshold: int = 5
    min_order_qty: int = 1
    max_order_qty: Optional[int] = None
    status: str = "active"
    sort_order: int = 0

    @field_validator("price")
    @classmethod
    def price_positive(cls, v):
        if v < 0:
            raise ValueError("Цена не может быть отрицательной")
        return v


class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    section: Optional[str] = None
    names: Optional[LangDict] = None
    descriptions: Optional[LangDict] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    quantity: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    min_order_qty: Optional[int] = None
    max_order_qty: Optional[int] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None


class StockAdjust(BaseModel):
    delta: int  # +N пополнение, -N списание (не связанное с заказом)
    reason: str = "admin_adjustment"


# ---------- Корзина / Заказ ----------

class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreateIn(BaseModel):
    items: List[CartItemIn]
    customer_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=3, max_length=64)
    address: Optional[str] = None
    delivery_type: str = "delivery"  # delivery | pickup
    comment: Optional[str] = None
    payment_method: str  # cash | transfer
    language: str = "ru"


class OrderItemOut(BaseModel):
    product_id: Optional[int]
    product_name: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_name: str
    phone: str
    address: Optional[str] = None
    delivery_type: str
    comment: Optional[str] = None
    payment_method: str
    payment_status: str
    receipt_url: Optional[str] = None
    status: str
    subtotal: Decimal
    total: Decimal
    currency: str
    items: List[OrderItemOut]
    created_at: datetime
    telegram_id: Optional[int] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None


# ---------- Настройки ----------

class BusinessSettingsOut(BaseModel):
    business_name: str
    logo_url: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    instagram: Optional[str] = None
    address: Optional[str] = None
    work_open: Optional[str] = None
    work_close: Optional[str] = None
    is_open_override: Optional[str] = None  # "auto" | "open" | "closed"
    allow_orders_outside_hours: bool = True
    pickup_enabled: bool = True
    bank_name: Optional[str] = None
    bank_recipient: Optional[str] = None
    bank_iban: Optional[str] = None
    bank_account: Optional[str] = None
    bank_extra: Optional[str] = None
    welcome_text: Optional[str] = None
    default_language: str = "ru"
    currency: str = "SAR"
    is_open_now: bool = True


class BusinessSettingsUpdate(BaseModel):
    business_name: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    instagram: Optional[str] = None
    address: Optional[str] = None
    work_open: Optional[str] = None
    work_close: Optional[str] = None
    is_open_override: Optional[str] = None
    allow_orders_outside_hours: Optional[bool] = None
    pickup_enabled: Optional[bool] = None
    bank_name: Optional[str] = None
    bank_recipient: Optional[str] = None
    bank_iban: Optional[str] = None
    bank_account: Optional[str] = None
    bank_extra: Optional[str] = None
    welcome_text: Optional[str] = None
    default_language: Optional[str] = None
    currency: Optional[str] = None


# ---------- Профиль ----------

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    language: Optional[str] = None


class ProfileOut(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    language: str
    is_admin: bool = False


# ---------- Статистика ----------

class TopProductOut(BaseModel):
    product_id: Optional[int]
    name: str
    total_qty: int
    total_revenue: Decimal


class StatsOut(BaseModel):
    today_orders: int
    today_revenue: Decimal
    week_orders: int
    week_revenue: Decimal
    month_orders: int
    month_revenue: Decimal
    orders_by_status: Dict[str, int]
    top_products: List[TopProductOut]
    low_stock_products: List[ProductOut]