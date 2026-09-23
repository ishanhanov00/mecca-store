"""
Бизнес-логика и запросы к БД: товары, категории, заказы (с безопасной
транзакционной проверкой остатков), статистика.

КЛЮЧЕВОЙ ПРИНЦИП БЕЗОПАСНОСТИ: цена и наличие товара берутся ТОЛЬКО из БД.
Клиент присылает только product_id и желаемое количество — ничего больше
не используется при расчёте суммы заказа.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import TelegramUser, get_or_create_user
from app.utils import generate_order_number, pick_lang


# ---------------- Категории ----------------

def serialize_category(cat: models.Category) -> schemas.CategoryOut:
    return schemas.CategoryOut(
        id=cat.id, key=cat.key, section=cat.section.value, names=cat.names or {},
        icon=cat.icon, sort_order=cat.sort_order, is_active=cat.is_active, is_system=cat.is_system,
    )


def list_categories(db: Session, section: Optional[str] = None, only_active: bool = True) -> List[models.Category]:
    q = db.query(models.Category)
    if section:
        q = q.filter(models.Category.section == models.Section(section))
    if only_active:
        q = q.filter(models.Category.is_active.is_(True))
    return q.order_by(models.Category.sort_order.asc(), models.Category.id.asc()).all()


def create_category(db: Session, data: schemas.CategoryCreate) -> models.Category:
    if db.query(models.Category).filter(models.Category.key == data.key).first():
        raise HTTPException(status_code=400, detail="Категория с таким ключом уже существует")
    try:
        section_enum = models.Section(data.section)
    except ValueError:
        raise HTTPException(status_code=400, detail="Раздел должен быть 'menu' или 'sadaka'")
    cat = models.Category(
        key=data.key, section=section_enum, names=data.names, icon=data.icon,
        sort_order=data.sort_order, is_active=True, is_system=False,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def update_category(db: Session, cat_id: int, data: schemas.CategoryUpdate) -> models.Category:
    cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    if data.names is not None:
        cat.names = data.names
    if data.icon is not None:
        cat.icon = data.icon
    if data.sort_order is not None:
        cat.sort_order = data.sort_order
    if data.is_active is not None:
        cat.is_active = data.is_active
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, cat_id: int) -> None:
    cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    if cat.is_system:
        raise HTTPException(status_code=400, detail="Системную категорию меню удалить нельзя, можно скрыть")
    has_products = db.query(models.Product.id).filter(models.Product.category_id == cat_id).first()
    if has_products:
        raise HTTPException(status_code=400, detail="В категории есть товары — сначала перенесите или удалите их")
    db.delete(cat)
    db.commit()


# ---------------- Товары ----------------

def serialize_product(product: models.Product, lang: str, full_langs: bool = False) -> schemas.ProductOut:
    image_url = f"/uploads/products/{product.image_path}" if product.image_path else None
    return schemas.ProductOut(
        id=product.id,
        category_id=product.category_id,
        category_key=product.category.key if product.category else None,
        section=product.section.value,
        name=pick_lang(product.names, lang),
        description=pick_lang(product.descriptions, lang),
        names=product.names if full_langs else None,
        descriptions=product.descriptions if full_langs else None,
        price=product.price,
        currency=product.currency,
        quantity=product.quantity,
        low_stock_threshold=product.low_stock_threshold,
        min_order_qty=product.min_order_qty,
        max_order_qty=product.max_order_qty,
        status=product.status.value,
        image_url=image_url,
        sort_order=product.sort_order,
    )


def list_products(
    db: Session, section: Optional[str] = None, category_id: Optional[int] = None,
    only_active: bool = True,
) -> List[models.Product]:
    q = db.query(models.Product)
    if section:
        q = q.filter(models.Product.section == models.Section(section))
    if category_id:
        q = q.filter(models.Product.category_id == category_id)
    if only_active:
        q = q.filter(models.Product.status == models.ProductStatus.active)
    return q.order_by(models.Product.sort_order.asc(), models.Product.id.asc()).all()


def get_product_or_404(db: Session, product_id: int) -> models.Product:
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


def create_product(db: Session, data: schemas.ProductCreate) -> models.Product:
    category = db.query(models.Category).filter(models.Category.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Категория не найдена")
    try:
        section_enum = models.Section(data.section)
        status_enum = models.ProductStatus(data.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный раздел или статус")
    product = models.Product(
        category_id=data.category_id, section=section_enum,
        names=data.names, descriptions=data.descriptions or {},
        price=data.price, currency=data.currency, quantity=max(0, data.quantity),
        low_stock_threshold=data.low_stock_threshold, min_order_qty=max(1, data.min_order_qty),
        max_order_qty=data.max_order_qty, status=status_enum, sort_order=data.sort_order,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, data: schemas.ProductUpdate) -> models.Product:
    product = get_product_or_404(db, product_id)
    if data.category_id is not None:
        if not db.query(models.Category.id).filter(models.Category.id == data.category_id).first():
            raise HTTPException(status_code=400, detail="Категория не найдена")
        product.category_id = data.category_id
    if data.section is not None:
        product.section = models.Section(data.section)
    if data.names is not None:
        product.names = data.names
    if data.descriptions is not None:
        product.descriptions = data.descriptions
    if data.price is not None:
        if data.price < 0:
            raise HTTPException(status_code=400, detail="Цена не может быть отрицательной")
        product.price = data.price
    if data.currency is not None:
        product.currency = data.currency
    if data.quantity is not None:
        if data.quantity < 0:
            raise HTTPException(status_code=400, detail="Остаток не может быть отрицательным")
        product.quantity = data.quantity
        db.add(models.InventoryTransaction(
            product_id=product.id, order_id=None, change_qty=0,
            reason="admin_set_quantity", balance_after=data.quantity,
        ))
    if data.low_stock_threshold is not None:
        product.low_stock_threshold = data.low_stock_threshold
    if data.min_order_qty is not None:
        product.min_order_qty = max(1, data.min_order_qty)
    if data.max_order_qty is not None:
        product.max_order_qty = data.max_order_qty
    if data.status is not None:
        product.status = models.ProductStatus(data.status)
    if data.sort_order is not None:
        product.sort_order = data.sort_order
    db.commit()
    db.refresh(product)
    return product


def adjust_stock(db: Session, product_id: int, delta: int, reason: str = "admin_adjustment") -> models.Product:
    product = get_product_or_404(db, product_id)
    new_qty = product.quantity + delta
    if new_qty < 0:
        raise HTTPException(status_code=400, detail=f"Недостаточно товара для списания (сейчас {product.quantity})")
    product.quantity = new_qty
    db.add(models.InventoryTransaction(
        product_id=product.id, order_id=None, change_qty=delta,
        reason=reason, balance_after=new_qty,
    ))
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = get_product_or_404(db, product_id)
    used_in_orders = db.query(models.OrderItem.id).filter(models.OrderItem.product_id == product_id).first()
    if used_in_orders:
        # Не удаляем физически товар, у которого есть история заказов — скрываем,
        # чтобы не сломать историю заказов клиентов.
        product.status = models.ProductStatus.hidden
        db.commit()
        return
    db.delete(product)
    db.commit()


def set_product_image(db: Session, product_id: int, filename: str) -> models.Product:
    product = get_product_or_404(db, product_id)
    product.image_path = filename
    db.commit()
    db.refresh(product)
    return product


# ---------------- Заказы ----------------

def _order_to_out(order: models.Order) -> schemas.OrderOut:
    return schemas.OrderOut(
        id=order.id, order_number=order.order_number, customer_name=order.customer_name,
        phone=order.phone, address=order.address, delivery_type=order.delivery_type.value,
        comment=order.comment, payment_method=order.payment_method.value,
        payment_status=order.payment_status.value,
        receipt_url=f"/uploads/receipts/{order.receipt_path}" if order.receipt_path else None,
        status=order.status.value, subtotal=order.subtotal, total=order.total, currency=order.currency,
        items=[schemas.OrderItemOut.model_validate(i) for i in order.items],
        created_at=order.created_at, telegram_id=order.telegram_id, username=order.username,
    )


def create_order(
    db: Session, tg_user: TelegramUser, order_in: schemas.OrderCreateIn, currency: str,
) -> schemas.OrderOut:
    if not order_in.items:
        raise HTTPException(status_code=400, detail="Корзина пуста")
    if order_in.payment_method not in ("cash", "transfer"):
        raise HTTPException(status_code=400, detail="Некорректный способ оплаты")
    delivery_type = order_in.delivery_type if order_in.delivery_type in ("delivery", "pickup") else "delivery"
    lang = order_in.language if order_in.language in ("ru", "uz", "ar", "en") else "ru"

    user = get_or_create_user(db, tg_user)

    # Схлопываем дубликаты product_id на случай, если клиент прислал товар дважды
    merged: dict = {}
    for item in order_in.items:
        merged[item.product_id] = merged.get(item.product_id, 0) + item.quantity

    items_payload = []
    subtotal = Decimal("0")

    for product_id, qty in merged.items():
        if qty <= 0:
            continue
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if not product:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Товар #{product_id} не найден")
        name = pick_lang(product.names, lang)
        if product.status != models.ProductStatus.active:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"«{name}» сейчас недоступен")
        if qty < product.min_order_qty:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Минимальное количество для «{name}»: {product.min_order_qty}")
        if product.max_order_qty and qty > product.max_order_qty:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Максимальное количество для «{name}»: {product.max_order_qty}")

        # Атомарное списание остатка прямо в SQL-запросе: гарантирует, что даже при
        # одновременных заказах остаток никогда не станет отрицательным.
        result = db.execute(
            sa_update(models.Product)
            .where(models.Product.id == product.id, models.Product.quantity >= qty)
            .values(quantity=models.Product.quantity - qty)
        )
        if result.rowcount == 0:
            db.rollback()
            fresh = db.query(models.Product).filter(models.Product.id == product.id).first()
            remaining = fresh.quantity if fresh else 0
            if remaining <= 0:
                raise HTTPException(status_code=409, detail=f"«{name}» закончился, уберите его из корзины")
            raise HTTPException(status_code=409, detail=f"Извините, осталось только {remaining} шт. товара «{name}»")

        db.refresh(product)
        line_subtotal = (product.price * qty).quantize(Decimal("0.01"))
        subtotal += line_subtotal
        items_payload.append({
            "product_id": product.id, "product_name": name, "unit_price": product.price,
            "quantity": qty, "subtotal": line_subtotal, "balance_after": product.quantity,
        })

    if not items_payload:
        db.rollback()
        raise HTTPException(status_code=400, detail="Корзина пуста")

    order = models.Order(
        order_number=generate_order_number(db),
        user_id=user.id, telegram_id=tg_user.telegram_id, username=tg_user.username,
        customer_name=order_in.customer_name.strip()[:255],
        phone=order_in.phone.strip()[:64],
        address=(order_in.address or "").strip()[:512] or None,
        delivery_type=models.DeliveryType(delivery_type),
        comment=(order_in.comment or "").strip()[:2000] or None,
        payment_method=models.PaymentMethod(order_in.payment_method),
        payment_status=(models.PaymentStatus.awaiting_transfer if order_in.payment_method == "transfer"
                        else models.PaymentStatus.unpaid),
        status=models.OrderStatus.new,
        subtotal=subtotal, total=subtotal, currency=currency, language=lang,
    )
    db.add(order)
    db.flush()

    for item_data in items_payload:
        db.add(models.OrderItem(
            order_id=order.id, product_id=item_data["product_id"],
            product_name=item_data["product_name"], unit_price=item_data["unit_price"],
            quantity=item_data["quantity"], subtotal=item_data["subtotal"],
        ))
        db.add(models.InventoryTransaction(
            product_id=item_data["product_id"], order_id=order.id,
            change_qty=-item_data["quantity"], reason="order_created",
            balance_after=item_data["balance_after"],
        ))

    user.full_name = order.customer_name
    user.phone = order.phone
    if order_in.language:
        user.language = lang

    db.commit()
    db.refresh(order)
    return _order_to_out(order)


def get_order_or_404(db: Session, order_id: int) -> models.Order:
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return order


def get_order_out(db: Session, order_id: int) -> schemas.OrderOut:
    return _order_to_out(get_order_or_404(db, order_id))


def list_orders(
    db: Session, telegram_id: Optional[int] = None, status: Optional[str] = None, limit: int = 100,
) -> List[models.Order]:
    q = db.query(models.Order)
    if telegram_id is not None:
        q = q.filter(models.Order.telegram_id == telegram_id)
    if status:
        q = q.filter(models.Order.status == models.OrderStatus(status))
    return q.order_by(models.Order.created_at.desc()).limit(limit).all()


def attach_receipt(db: Session, order_id: int, filename: str) -> schemas.OrderOut:
    order = get_order_or_404(db, order_id)
    order.receipt_path = filename
    order.payment_status = models.PaymentStatus.pending_review
    db.commit()
    db.refresh(order)
    return _order_to_out(order)


def update_order_status(
    db: Session, order_id: int, status: Optional[str], payment_status: Optional[str],
) -> models.Order:
    order = get_order_or_404(db, order_id)

    if status is not None:
        try:
            new_status = models.OrderStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный статус заказа")
        if new_status == models.OrderStatus.cancelled and order.status != models.OrderStatus.cancelled:
            _restore_stock(db, order)
        order.status = new_status

    if payment_status is not None:
        try:
            order.payment_status = models.PaymentStatus(payment_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный статус оплаты")

    db.commit()
    db.refresh(order)
    return order


def _restore_stock(db: Session, order: models.Order) -> None:
    """Возвращает товары на склад при отмене заказа (один раз на заказ)."""
    if order.stock_restored:
        return
    for item in order.items:
        if not item.product_id:
            continue
        db.execute(
            sa_update(models.Product)
            .where(models.Product.id == item.product_id)
            .values(quantity=models.Product.quantity + item.quantity)
        )
        fresh = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        db.add(models.InventoryTransaction(
            product_id=item.product_id, order_id=order.id, change_qty=item.quantity,
            reason="order_cancelled", balance_after=fresh.quantity if fresh else item.quantity,
        ))
    order.stock_restored = True


# ---------------- Статистика ----------------

def get_stats(db: Session) -> dict:
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = datetime(now.year, now.month, 1)

    def agg(since: datetime):
        cnt, revenue = (
            db.query(func.count(models.Order.id), func.coalesce(func.sum(models.Order.total), 0))
            .filter(models.Order.created_at >= since, models.Order.status != models.OrderStatus.cancelled)
            .first()
        )
        return cnt or 0, revenue or Decimal("0")

    today_orders, today_revenue = agg(today_start)
    week_orders, week_revenue = agg(week_start)
    month_orders, month_revenue = agg(month_start)

    status_rows = db.query(models.Order.status, func.count(models.Order.id)).group_by(models.Order.status).all()
    orders_by_status = {s.value: c for s, c in status_rows}

    top_rows = (
        db.query(
            models.OrderItem.product_id, models.OrderItem.product_name,
            func.sum(models.OrderItem.quantity).label("qty"),
            func.sum(models.OrderItem.subtotal).label("revenue"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(models.Order.status != models.OrderStatus.cancelled)
        .group_by(models.OrderItem.product_id, models.OrderItem.product_name)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .limit(10)
        .all()
    )
    top_products = [
        schemas.TopProductOut(product_id=r[0], name=r[1], total_qty=int(r[2]), total_revenue=r[3])
        for r in top_rows
    ]

    low_stock = (
        db.query(models.Product)
        .filter(models.Product.status == models.ProductStatus.active,
                models.Product.quantity <= models.Product.low_stock_threshold)
        .order_by(models.Product.quantity.asc())
        .all()
    )

    return {
        "today_orders": today_orders, "today_revenue": today_revenue,
        "week_orders": week_orders, "week_revenue": week_revenue,
        "month_orders": month_orders, "month_revenue": month_revenue,
        "orders_by_status": orders_by_status, "top_products": top_products,
        "low_stock_products": [serialize_product(p, "ru") for p in low_stock],
    }