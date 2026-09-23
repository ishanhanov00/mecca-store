from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app import models, schemas, crud
from app.auth import (
    TelegramUser,
    get_current_telegram_user,
    get_or_create_user,
    require_admin,
)
from app.seed import run_seed
from app.utils import (
    get_settings_dict,
    set_settings,
    is_shop_open,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title=settings.BUSINESS_NAME,
    version="1.0.0",
    description="Mecca Shop API",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# UPLOADS
# ============================================================

settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

(settings.UPLOADS_DIR / "products").mkdir(
    parents=True,
    exist_ok=True,
)

(settings.UPLOADS_DIR / "receipts").mkdir(
    parents=True,
    exist_ok=True,
)

app.mount(
    "/uploads",
    StaticFiles(directory=str(settings.UPLOADS_DIR)),
    name="uploads",
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():
    # Создаём таблицы
    Base.metadata.create_all(bind=engine)

    # Заполняем первоначальные категории
    db = next(get_db())

    try:
        run_seed(db)
    finally:
        db.close()


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": settings.BUSINESS_NAME,
        "message": "API is running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


# ============================================================
# PROFILE
# ============================================================

@app.get("/api/profile", response_model=schemas.ProfileOut)
def get_profile(
    user: TelegramUser = Depends(get_current_telegram_user),
    db: Session = Depends(get_db),
):
    db_user = get_or_create_user(db, user)

    return schemas.ProfileOut(
        telegram_id=db_user.telegram_id,
        username=db_user.username,
        full_name=db_user.full_name,
        phone=db_user.phone,
        language=db_user.language,
        is_admin=user.is_admin,
    )


@app.patch("/api/profile", response_model=schemas.ProfileOut)
def update_profile(
    data: schemas.ProfileUpdate,
    user: TelegramUser = Depends(get_current_telegram_user),
    db: Session = Depends(get_db),
):
    db_user = get_or_create_user(db, user)

    if data.full_name is not None:
        db_user.full_name = data.full_name.strip()[:255]

    if data.phone is not None:
        db_user.phone = data.phone.strip()[:64]

    if data.language is not None:
        if data.language not in ("ru", "uz", "ar", "en"):
            raise HTTPException(
                status_code=400,
                detail="Неподдерживаемый язык",
            )

        db_user.language = data.language

    db.commit()
    db.refresh(db_user)

    return schemas.ProfileOut(
        telegram_id=db_user.telegram_id,
        username=db_user.username,
        full_name=db_user.full_name,
        phone=db_user.phone,
        language=db_user.language,
        is_admin=user.is_admin,
    )


# ============================================================
# CATEGORIES
# ============================================================

@app.get("/api/categories")
def get_categories(
    section: Optional[str] = None,
    db: Session = Depends(get_db),
):
    categories = crud.list_categories(
        db,
        section=section,
        only_active=True,
    )

    return [
        crud.serialize_category(category)
        for category in categories
    ]


@app.post(
    "/api/admin/categories",
    response_model=schemas.CategoryOut,
)
def create_category(
    data: schemas.CategoryCreate,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = crud.create_category(db, data)
    return crud.serialize_category(category)


@app.patch(
    "/api/admin/categories/{category_id}",
    response_model=schemas.CategoryOut,
)
def update_category(
    category_id: int,
    data: schemas.CategoryUpdate,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = crud.update_category(
        db,
        category_id,
        data,
    )

    return crud.serialize_category(category)


@app.delete("/api/admin/categories/{category_id}")
def delete_category(
    category_id: int,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    crud.delete_category(db, category_id)

    return {
        "ok": True,
        "message": "Категория удалена",
    }


# ============================================================
# PRODUCTS
# ============================================================

@app.get("/api/products")
def get_products(
    section: Optional[str] = None,
    category_id: Optional[int] = None,
    lang: str = "ru",
    db: Session = Depends(get_db),
):
    if lang not in ("ru", "uz", "ar", "en"):
        lang = "ru"

    products = crud.list_products(
        db,
        section=section,
        category_id=category_id,
        only_active=True,
    )

    return [
        crud.serialize_product(
            product,
            lang,
            full_langs=False,
        )
        for product in products
    ]


@app.get("/api/products/{product_id}")
def get_product(
    product_id: int,
    lang: str = "ru",
    db: Session = Depends(get_db),
):
    if lang not in ("ru", "uz", "ar", "en"):
        lang = "ru"

    product = crud.get_product_or_404(
        db,
        product_id,
    )

    return crud.serialize_product(
        product,
        lang,
        full_langs=False,
    )


@app.post(
    "/api/admin/products",
    response_model=schemas.ProductOut,
)
def create_product(
    data: schemas.ProductCreate,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = crud.create_product(
        db,
        data,
    )

    return crud.serialize_product(
        product,
        "ru",
        full_langs=True,
    )


@app.patch(
    "/api/admin/products/{product_id}",
    response_model=schemas.ProductOut,
)
def update_product(
    product_id: int,
    data: schemas.ProductUpdate,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = crud.update_product(
        db,
        product_id,
        data,
    )

    return crud.serialize_product(
        product,
        "ru",
        full_langs=True,
    )


@app.delete("/api/admin/products/{product_id}")
def delete_product(
    product_id: int,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    crud.delete_product(
        db,
        product_id,
    )

    return {
        "ok": True,
        "message": "Товар удалён или скрыт",
    }


@app.post("/api/admin/products/{product_id}/stock")
def adjust_product_stock(
    product_id: int,
    data: schemas.StockAdjust,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = crud.adjust_stock(
        db,
        product_id,
        data.delta,
        data.reason,
    )

    return crud.serialize_product(
        product,
        "ru",
        full_langs=True,
    )


# ============================================================
# PRODUCT IMAGE
# ============================================================

@app.post("/api/admin/products/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = crud.get_product_or_404(
        db,
        product_id,
    )

    if not file.content_type:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить тип файла",
        )

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Разрешены только JPG, PNG и WEBP",
        )

    extension = allowed_types[file.content_type]

    filename = f"product_{product.id}{extension}"

    path = (
        settings.UPLOADS_DIR
        / "products"
        / filename
    )

    content = await file.read()

    max_size = settings.MAX_UPLOAD_MB * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум {settings.MAX_UPLOAD_MB} MB",
        )

    path.write_bytes(content)

    crud.set_product_image(
        db,
        product.id,
        filename,
    )

    return {
        "ok": True,
        "image_url": f"/uploads/products/{filename}",
    }


# ============================================================
# ORDERS
# ============================================================

@app.post(
    "/api/orders",
    response_model=schemas.OrderOut,
)
async def create_order(
    data: schemas.OrderCreateIn,
    user: TelegramUser = Depends(get_current_telegram_user),
    db: Session = Depends(get_db),
):
    order = crud.create_order(
        db,
        user,
        data,
        settings.CURRENCY,
    )

    # Уведомление администраторам
    from app.utils import notify_admins_new_order

    await notify_admins_new_order(
        db.query(models.Order)
        .filter(models.Order.id == order.id)
        .first()
    )

    return order


@app.get(
    "/api/orders",
    response_model=list[schemas.OrderOut],
)
def get_my_orders(
    user: TelegramUser = Depends(get_current_telegram_user),
    db: Session = Depends(get_db),
):
    orders = crud.list_orders(
        db,
        telegram_id=user.telegram_id,
        limit=100,
    )

    return [
        crud.get_order_out(db, order.id)
        for order in orders
    ]


@app.get(
    "/api/orders/{order_id}",
    response_model=schemas.OrderOut,
)
def get_my_order(
    order_id: int,
    user: TelegramUser = Depends(get_current_telegram_user),
    db: Session = Depends(get_db),
):
    order = crud.get_order_or_404(
        db,
        order_id,
    )

    if (
        order.telegram_id != user.telegram_id
        and not user.is_admin
    ):
        raise HTTPException(
            status_code=403,
            detail="Нет доступа к этому заказу",
        )

    return crud.get_order_out(
        db,
        order_id,
    )


# ============================================================
# RECEIPT
# ============================================================

@app.post("/api/orders/{order_id}/receipt")
async def upload_receipt(
    order_id: int,
    file: UploadFile = File(...),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: Session = Depends(get_db),
):
    order = crud.get_order_or_404(
        db,
        order_id,
    )

    if order.telegram_id != user.telegram_id:
        raise HTTPException(
            status_code=403,
            detail="Нет доступа к этому заказу",
        )

    if not file.content_type:
        raise HTTPException(
            status_code=400,
            detail="Неизвестный тип файла",
        )

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
        "image/webp": ".webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Разрешены JPG, PNG, WEBP и PDF",
        )

    extension = allowed_types[file.content_type]

    filename = f"receipt_{order.id}{extension}"

    path = (
        settings.UPLOADS_DIR
        / "receipts"
        / filename
    )

    content = await file.read()

    max_size = settings.MAX_UPLOAD_MB * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум {settings.MAX_UPLOAD_MB} MB",
        )

    path.write_bytes(content)

    result = crud.attach_receipt(
        db,
        order.id,
        filename,
    )

    return result


# ============================================================
# ADMIN ORDERS
# ============================================================

@app.get(
    "/api/admin/orders",
    response_model=list[schemas.OrderOut],
)
def admin_orders(
    status: Optional[str] = None,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    orders = crud.list_orders(
        db,
        status=status,
        limit=500,
    )

    return [
        crud.get_order_out(db, order.id)
        for order in orders
    ]


@app.patch(
    "/api/admin/orders/{order_id}",
    response_model=schemas.OrderOut,
)
async def admin_update_order(
    order_id: int,
    data: schemas.OrderStatusUpdate,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    old_order = crud.get_order_or_404(
        db,
        order_id,
    )

    old_status = old_order.status.value
    old_payment_status = old_order.payment_status.value

    order = crud.update_order_status(
        db,
        order_id,
        data.status,
        data.payment_status,
    )

    # Уведомление клиента
    if (
        order.telegram_id
        and (
            old_status != order.status.value
            or old_payment_status != order.payment_status.value
        )
    ):
        from app.utils import (
            notify_customer_status_change,
            send_telegram_message,
        )
        from app.translations import (
            status_label,
            PAYMENT_CONFIRMED_TEXT,
            PAYMENT_REJECTED_TEXT,
            STATUS_CHANGED_TEXT,
        )

        lang = order.language if order.language in (
            "ru",
            "uz",
            "ar",
            "en",
        ) else "ru"

        if (
            old_payment_status != order.payment_status.value
            and order.payment_status.value == "confirmed"
        ):
            message = PAYMENT_CONFIRMED_TEXT[lang].format(
                n=order.order_number
            )

        elif (
            old_payment_status != order.payment_status.value
            and order.payment_status.value == "rejected"
        ):
            message = PAYMENT_REJECTED_TEXT[lang].format(
                n=order.order_number
            )

        else:
            message = STATUS_CHANGED_TEXT[lang].format(
                n=order.order_number,
                status=status_label(
                    order.status.value,
                    lang,
                ),
            )

        await notify_customer_status_change(
            order,
            message,
        )

    return crud.get_order_out(
        db,
        order.id,
    )


# ============================================================
# ADMIN STATISTICS
# ============================================================

@app.get("/api/admin/stats")
def admin_stats(
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return crud.get_stats(db)


# ============================================================
# BUSINESS SETTINGS
# ============================================================

@app.get(
    "/api/settings",
    response_model=schemas.BusinessSettingsOut,
)
def get_business_settings(
    db: Session = Depends(get_db),
):
    data = get_settings_dict(db)

    return schemas.BusinessSettingsOut(
        business_name=data.get("business_name", settings.BUSINESS_NAME),
        logo_url=data.get("logo_url") or None,
        description=data.get("description") or None,
        phone=data.get("phone") or None,
        whatsapp=data.get("whatsapp") or None,
        instagram=data.get("instagram") or None,
        address=data.get("address") or None,
        work_open=data.get("work_open") or None,
        work_close=data.get("work_close") or None,
        is_open_override=data.get("is_open_override") or "auto",
        allow_orders_outside_hours=data.get(
            "allow_orders_outside_hours",
            "true",
        ).lower() == "true",
        pickup_enabled=data.get(
            "pickup_enabled",
            "true",
        ).lower() == "true",
        bank_name=data.get("bank_name") or None,
        bank_recipient=data.get("bank_recipient") or None,
        bank_iban=data.get("bank_iban") or None,
        bank_account=data.get("bank_account") or None,
        bank_extra=data.get("bank_extra") or None,
        welcome_text=data.get("welcome_text") or None,
        default_language=data.get(
            "default_language",
            "ru",
        ),
        currency=data.get(
            "currency",
            "SAR",
        ),
        is_open_now=is_shop_open(data),
    )


@app.patch(
    "/api/admin/settings",
    response_model=schemas.BusinessSettingsOut,
)
def update_business_settings(
    data: schemas.BusinessSettingsUpdate,
    user: TelegramUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    values = data.model_dump(
        exclude_none=True
    )

    set_settings(
        db,
        values,
    )

    return get_business_settings(db)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )