"""
Модели базы данных.

Таблицы: users, categories, products, orders, order_items,
inventory_transactions, settings.

Мультиязычные поля (название/описание товаров и категорий) хранятся как JSON
вида {"ru": "...", "uz": "...", "ar": "...", "en": "..."}.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Section(str, enum.Enum):
    menu = "menu"
    sadaka = "sadaka"


class ProductStatus(str, enum.Enum):
    active = "active"      # доступен
    hidden = "hidden"      # скрыт


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    transfer = "transfer"


class PaymentStatus(str, enum.Enum):
    unpaid = "unpaid"                    # для наличных — оплата при получении
    awaiting_transfer = "awaiting_transfer"  # выбран перевод, чек ещё не загружен
    pending_review = "pending_review"    # чек загружен, ждёт проверки админом
    confirmed = "confirmed"              # оплата подтверждена админом
    rejected = "rejected"                # оплата отклонена админом


class OrderStatus(str, enum.Enum):
    new = "new"                 # 🆕 Новый
    confirmed = "confirmed"     # ✅ Оплачен / подтверждён
    preparing = "preparing"     # 👨🍳 Готовится
    ready = "ready"              # 📦 Готов
    delivering = "delivering"   # 🚚 Доставляется
    completed = "completed"     # ✅ Выполнен
    cancelled = "cancelled"     # ❌ Отменён


class DeliveryType(str, enum.Enum):
    delivery = "delivery"
    pickup = "pickup"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=True)
    full_name = Column(String(255), nullable=True)  # имя, указанное клиентом при заказе
    language = Column(String(8), default="ru", nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    orders = relationship("Order", back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    section = Column(Enum(Section), nullable=False, index=True)
    names = Column(JSON, nullable=False, default=dict)  # {"ru": "...", "uz": ..., ...}
    icon = Column(String(16), nullable=True)  # эмодзи-иконка
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)  # системные категории меню нельзя удалить

    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    section = Column(Enum(Section), nullable=False, index=True)

    names = Column(JSON, nullable=False, default=dict)
    descriptions = Column(JSON, nullable=False, default=dict)

    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), default="SAR", nullable=False)

    quantity = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, nullable=False, default=5)

    min_order_qty = Column(Integer, nullable=False, default=1)
    max_order_qty = Column(Integer, nullable=True)  # None = без ограничения

    status = Column(Enum(ProductStatus), default=ProductStatus.active, nullable=False, index=True)
    image_path = Column(String(512), nullable=True)  # относительный путь в /uploads/products
    sort_order = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = relationship("Category", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String(32), unique=True, index=True, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    telegram_id = Column(Integer, nullable=True, index=True)
    username = Column(String(255), nullable=True)

    customer_name = Column(String(255), nullable=False)
    phone = Column(String(64), nullable=False)
    address = Column(String(512), nullable=True)
    delivery_type = Column(Enum(DeliveryType), default=DeliveryType.delivery, nullable=False)
    comment = Column(Text, nullable=True)

    payment_method = Column(Enum(PaymentMethod), nullable=False)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.unpaid, nullable=False, index=True)
    receipt_path = Column(String(512), nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.new, nullable=False, index=True)

    subtotal = Column(Numeric(10, 2), nullable=False, default=0)
    total = Column(Numeric(10, 2), nullable=False, default=0)
    currency = Column(String(8), default="SAR", nullable=False)

    language = Column(String(8), default="ru", nullable=False)
    stock_restored = Column(Boolean, default=False, nullable=False)  # чтобы не вернуть остаток дважды

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    # Снимок данных товара на момент заказа (цена могла измениться позже)
    product_name = Column(String(255), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class InventoryTransaction(Base):
    """Журнал изменений остатков — для аудита и защиты от гонок при заказе."""
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    change_qty = Column(Integer, nullable=False)  # отрицательное = списание, положительное = возврат/пополнение
    reason = Column(String(64), nullable=False)   # order_created, order_cancelled, admin_adjustment
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Settings(Base):
    """Простое key-value хранилище настроек бизнеса."""
    __tablename__ = "settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=True)


class AdminActionLog(Base):
    """Необязательный лог админских действий — полезно для истории/отладки."""
    __tablename__ = "admin_action_log"

    id = Column(Integer, primary_key=True)
    admin_telegram_id = Column(Integer, nullable=False)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)