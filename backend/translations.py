"""
Тексты для уведомлений клиенту на разных языках (для UI-строк Mini App
переводы лежат отдельно в frontend/js/i18n/*.json).
"""

STATUS_LABELS = {
    "ru": {
        "new": "🆕 Новый", "confirmed": "✅ Оплачен/подтверждён", "preparing": "👨🍳 Готовится",
        "ready": "📦 Готов", "delivering": "🚚 Доставляется", "completed": "✅ Выполнен",
        "cancelled": "❌ Отменён",
    },
    "uz": {
        "new": "🆕 Yangi", "confirmed": "✅ Tasdiqlandi", "preparing": "👨🍳 Tayyorlanmoqda",
        "ready": "📦 Tayyor", "delivering": "🚚 Yetkazilmoqda", "completed": "✅ Bajarildi",
        "cancelled": "❌ Bekor qilindi",
    },
    "ar": {
        "new": "🆕 جديد", "confirmed": "✅ تم الدفع/التأكيد", "preparing": "👨🍳 قيد التحضير",
        "ready": "📦 جاهز", "delivering": "🚚 يتم التوصيل", "completed": "✅ مكتمل",
        "cancelled": "❌ ملغى",
    },
    "en": {
        "new": "🆕 New", "confirmed": "✅ Confirmed/Paid", "preparing": "👨🍳 Preparing",
        "ready": "📦 Ready", "delivering": "🚚 Delivering", "completed": "✅ Completed",
        "cancelled": "❌ Cancelled",
    },
}

PAYMENT_CONFIRMED_TEXT = {
    "ru": "✅ Оплата по заказу №{n} подтверждена. Спасибо!",
    "uz": "✅ №{n} buyurtma uchun to'lov tasdiqlandi. Rahmat!",
    "ar": "✅ تم تأكيد الدفع للطلب رقم {n}. شكراً لك!",
    "en": "✅ Payment for order #{n} has been confirmed. Thank you!",
}

PAYMENT_REJECTED_TEXT = {
    "ru": "❌ Оплата по заказу №{n} не подтверждена. Пожалуйста, свяжитесь с нами или отправьте чек ещё раз.",
    "uz": "❌ №{n} buyurtma uchun to'lov tasdiqlanmadi. Iltimos, biz bilan bog'laning yoki chekni qayta yuboring.",
    "ar": "❌ لم يتم تأكيد الدفع للطلب رقم {n}. يرجى التواصل معنا أو إرسال الإيصال مرة أخرى.",
    "en": "❌ Payment for order #{n} was not confirmed. Please contact us or resend the receipt.",
}

STATUS_CHANGED_TEXT = {
    "ru": "ℹ Статус вашего заказа №{n} изменён: {status}",
    "uz": "ℹ №{n} buyurtmangiz holati o'zgardi: {status}",
    "ar": "ℹ تم تغيير حالة طلبك رقم {n}: {status}",
    "en": "ℹ Your order #{n} status changed: {status}",
}


def status_label(status: str, lang: str) -> str:
    return STATUS_LABELS.get(lang, STATUS_LABELS["ru"]).get(status, status)