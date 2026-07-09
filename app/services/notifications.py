import logging

from aiogram import Bot
from app.config import settings
from app.models import Order, TradeIn


async def notify_user_order_status(bot: Bot, telegram_id: int, order: Order):
    status_text = {
        "new": "новый",
        "confirmed": "подтверждён",
        "in_progress": "в работе",
        "ready": "готов",
        "delivering": "в доставке",
        "completed": "завершён",
        "cancelled": "отменён",
        "pending_sync": "ожидает отправки в CRM",
        "sync_error": "ошибка синхронизации",
    }.get(order.status.value, order.status.value)

    text = (
        f"Ваш заказ <b>#{order.order_number}</b>\n\n"
        f"Сумма: {order.total_amount} ₽\n"
        f"Статус: {status_text} ✅\n\n"
    )
    if order.status.value == "pending_sync":
        text += "Заказ сохранён и будет отправлен в CRM повторно."
    else:
        text += "Мы сообщим о дальнейших изменениях."
    await bot.send_message(telegram_id, text)


async def notify_admins_new_order(bot: Bot, order: Order, error: str | None = None):
    items_text = "\n".join(
        f"{i+1}. {item.name} — {item.quantity} шт. × {item.price} ₽"
        for i, item in enumerate(order.items)
    )
    livesklad_text = order.livesklad_order_id or "ожидание / ошибка"
    text = (
        f"Новый заказ <b>#{order.order_number}</b>\n\n"
        f"Клиент: {order.customer_name}\n"
        f"Телефон: {order.customer_phone}\n"
        f"Telegram: @{order.user.username or '-'}\n\n"
        f"Товары:\n{items_text}\n\n"
        f"Итого: {order.total_amount} ₽\n\n"
        f"Способ получения: {order.delivery_type}\n"
        f"Комментарий: {order.comment or '-'}\n"
        f"LiveSklad: {livesklad_text}"
    )
    if error:
        text += f"\n\n<b>Ошибка:</b> {error}"

    from app.bot.keyboards import admin_request_keyboard
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=admin_request_keyboard(order.id, order.livesklad_order_id),
            )
        except Exception:
            logging.exception("Failed to notify admin %s about order %s", admin_id, order.id)


async def notify_admins_tradein(bot: Bot, tradein: TradeIn):
    text = (
        f"<b>Новая заявка Trade-in</b>\n\n"
        f"Клиент: {tradein.user.name or '-'}\n"
        f"Телефон: {tradein.user.phone or '-'}\n"
        f"Telegram: @{tradein.user.username or '-'}\n\n"
        f"Тип устройства: {tradein.device_type}\n"
        f"Модель: {tradein.model}\n"
        f"Батарея: {tradein.battery_condition}\n"
        f"Состояние: {tradein.device_condition}\n"
        f"Оценочная цена: {tradein.estimated_price or 'не указана'}\n"
    )
    from app.bot.keyboards import admin_tradein_keyboard
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=admin_tradein_keyboard(tradein.id))
        except Exception:
            logging.exception("Failed to notify admin %s about trade-in %s", admin_id, tradein.id)
