from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.bot.handlers.client import is_admin
from app.bot.keyboards import admin_request_keyboard, admin_tradein_keyboard
from app.models import Order, OrderStatus, SyncStatus, SyncLog, TradeIn, TradeInStatus, Giveaway, Product, Shop, ProductStock
from app.services.livesklad import create_livesklad_order
from app.config import settings
from app.services.notifications import notify_user_order_status
from app.tasks import sync_google_sheets

router = Router()


@router.message(F.text == "📦 Новые заявки")
async def new_orders(message: types.Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    stmt = select(Order).where(Order.status == OrderStatus.NEW).order_by(desc(Order.created_at)).limit(20)
    result = await session.execute(stmt)
    orders = result.scalars().all()
    if not orders:
        await message.answer("Нет новых заявок.")
        return
    for order in orders:
        text = format_order(order)
        await message.answer(text, reply_markup=admin_request_keyboard(order.id, order.livesklad_order_id))


@router.message(F.text == "🔄 Trade-in заявки")
async def tradein_orders(message: types.Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    stmt = select(TradeIn).where(TradeIn.status == TradeInStatus.NEW).order_by(desc(TradeIn.created_at)).limit(20)
    result = await session.execute(stmt)
    tradeins = result.scalars().all()
    if not tradeins:
        await message.answer("Нет новых заявок Trade-in.")
        return
    for t in tradeins:
        text = format_tradein(t)
        await message.answer(text, reply_markup=admin_tradein_keyboard(t.id))


@router.message(F.text == "🎁 Розыгрыши")
async def admin_giveaways(message: types.Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    stmt = select(Giveaway).order_by(desc(Giveaway.created_at)).limit(10)
    result = await session.execute(stmt)
    giveaways = result.scalars().all()
    if not giveaways:
        await message.answer("Розыгрышей пока нет. Создайте через админку или API.")
        return
    text = "<b>Розыгрыши</b>\n\n"
    for g in giveaways:
        text += f"• {g.title} — {g.status.value}\n"
    await message.answer(text)


@router.message(F.text == "🔄 Синхронизация")
async def sync_menu(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Синхронизация:\n"
        "Google Sheets — обновляет товары и цены.\n"
        "LiveSklad — повторяет отправку неотправленных заказов.\n",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🔄 Обновить прайс", callback_data="sync_sheets")],
                [types.InlineKeyboardButton(text="🔄 Повторить LiveSklad", callback_data="sync_livesklad")],
                [types.InlineKeyboardButton(text="🚨 Последние ошибки", callback_data="show_errors")],
            ]
        ),
    )


@router.callback_query(F.data == "sync_sheets")
async def sync_sheets_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    sync_google_sheets.delay()
    await callback.answer("Синхронизация Google Sheets запущена")


@router.callback_query(F.data == "sync_livesklad")
async def sync_livesklad_callback(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    stmt = select(Order).where(Order.status == OrderStatus.PENDING_SYNC)
    result = await session.execute(stmt)
    orders = result.scalars().all()
    for order in orders:
        try:
            livesklad_id = await create_livesklad_order(order)
            order.livesklad_order_id = livesklad_id
            order.status = OrderStatus.NEW
            order.sync_status = SyncStatus.SUCCESS
            await notify_user_order_status(callback.message.bot, order.user.telegram_id, order)
        except Exception as e:
            order.sync_message = str(e)
        await session.commit()
    await callback.answer(f"Обработано заказов: {len(orders)}")


@router.callback_query(F.data == "show_errors")
async def show_errors(callback: types.CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа")
        return
    stmt = select(SyncLog).order_by(desc(SyncLog.created_at)).limit(20)
    result = await session.execute(stmt)
    logs = result.scalars().all()
    if not logs:
        await callback.message.edit_text("Ошибок не найдено.")
        return
    text = "<b>Последние ошибки:</b>\n\n"
    for log in logs:
        text += f"[{log.created_at}] {log.source} | {log.status.value} | {log.message}\n"
    await callback.message.edit_text(text)


@router.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":", 1)[1])
    stmt = select(Order).where(Order.id == order_id)
    result = await session.execute(stmt)
    order = result.scalar_one()
    order.status = OrderStatus.CONFIRMED
    await session.commit()
    await notify_user_order_status(callback.message.bot, order.user.telegram_id, order)
    await callback.answer("Заказ подтверждён")


@router.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":", 1)[1])
    stmt = select(Order).where(Order.id == order_id)
    result = await session.execute(stmt)
    order = result.scalar_one()
    order.status = OrderStatus.CANCELLED
    await session.commit()
    await notify_user_order_status(callback.message.bot, order.user.telegram_id, order)
    await callback.answer("Заказ отменён")


@router.callback_query(F.data.startswith("admin_resync:"))
async def admin_resync(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split(":", 1)[1])
    stmt = select(Order).where(Order.id == order_id)
    result = await session.execute(stmt)
    order = result.scalar_one()
    try:
        livesklad_id = await create_livesklad_order(order)
        order.livesklad_order_id = livesklad_id
        order.status = OrderStatus.NEW
        order.sync_status = SyncStatus.SUCCESS
        await session.commit()
        await notify_user_order_status(callback.message.bot, order.user.telegram_id, order)
        await callback.answer("Синхронизация успешна")
    except Exception as e:
        order.sync_message = str(e)
        await session.commit()
        await callback.answer("Ошибка синхронизации")


def format_order(order: Order) -> str:
    items_text = "\n".join(
        f"{i+1}. {item.name} — {item.quantity} шт. × {item.price} ₽"
        for i, item in enumerate(order.items)
    )
    livesklad_text = order.livesklad_order_id or "ожидание / ошибка"
    return (
        f"Новая заявка <b>#{order.order_number}</b>\n\n"
        f"Клиент: {order.customer_name}\n"
        f"Телефон: {order.customer_phone}\n"
        f"Telegram: @{order.user.username or '-'}\n\n"
        f"Товары:\n{items_text}\n\n"
        f"Итого: {order.total_amount} ₽\n\n"
        f"Способ получения: {order.delivery_type}\n"
        f"Комментарий: {order.comment or '-'}\n"
        f"LiveSklad: {livesklad_text}"
    )


def format_tradein(t: TradeIn) -> str:
    return (
        f"<b>Новая заявка Trade-in #{t.id}</b>\n\n"
        f"Клиент: {t.user.name or '-'}\n"
        f"Телефон: {t.user.phone or '-'}\n"
        f"Telegram: @{t.user.username or '-'}\n\n"
        f"Тип устройства: {t.device_type}\n"
        f"Модель: {t.model}\n"
        f"Батарея: {t.battery_condition}\n"
        f"Состояние: {t.device_condition}\n"
        f"Оценочная цена: {t.estimated_price or 'не указана'}"
    )


@router.callback_query(F.data.startswith("admin_tradein_process:"))
async def admin_tradein_process(callback: types.CallbackQuery, session: AsyncSession):
    tradein_id = int(callback.data.split(":", 1)[1])
    stmt = select(TradeIn).where(TradeIn.id == tradein_id)
    result = await session.execute(stmt)
    t = result.scalar_one()
    t.status = TradeInStatus.PROCESSED
    await session.commit()
    await callback.answer("Trade-in обработан")


@router.callback_query(F.data.startswith("admin_tradein_contact:"))
async def admin_tradein_contact(callback: types.CallbackQuery, session: AsyncSession):
    tradein_id = int(callback.data.split(":", 1)[1])
    stmt = select(TradeIn).where(TradeIn.id == tradein_id)
    result = await session.execute(stmt)
    t = result.scalar_one()
    await callback.message.answer(f"Связаться с клиентом Trade-in #{t.id}: {t.user.phone or '@'+t.user.username}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_tradein_cancel:"))
async def admin_tradein_cancel(callback: types.CallbackQuery, session: AsyncSession):
    tradein_id = int(callback.data.split(":", 1)[1])
    stmt = select(TradeIn).where(TradeIn.id == tradein_id)
    result = await session.execute(stmt)
    t = result.scalar_one()
    t.status = TradeInStatus.CANCELLED
    await session.commit()
    await callback.answer("Trade-in отменён")


@router.message(F.text == "/set_stock")
async def cmd_set_stock_help(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Использование:\n"
        "/set_stock <sku> <название_филиала> <количество>\n\n"
        "Пример:\n"
        "/set_store iphone_15_pro_256 Острова 3"
    )


@router.message(F.text.startswith("/set_stock "))
async def cmd_set_stock(message: types.Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer("Неверный формат. Используйте: /set_stock <sku> <филиал> <количество>")
        return
    _, sku, shop_name, qty_str = parts
    try:
        qty = int(qty_str)
    except ValueError:
        await message.answer("Количество должно быть числом")
        return

    product_result = await session.execute(select(Product).where(Product.sku == sku))
    product = product_result.scalar_one_or_none()
    if not product:
        await message.answer(f"Товар с SKU {sku} не найден")
        return

    shop_result = await session.execute(select(Shop).where(Shop.name.ilike(f"%{shop_name}%")))
    shop = shop_result.scalar_one_or_none()
    if not shop:
        await message.answer(f"Филиал '{shop_name}' не найден")
        return

    stock_result = await session.execute(select(ProductStock).where(
        ProductStock.product_id == product.id,
        ProductStock.shop_id == shop.id,
    ))
    stock = stock_result.scalar_one_or_none()
    if stock is None:
        stock = ProductStock(product_id=product.id, shop_id=shop.id, quantity=qty)
        session.add(stock)
    else:
        stock.quantity = qty

    await session.flush()

    # Recalculate total stock
    total_result = await session.execute(select(ProductStock).where(ProductStock.product_id == product.id))
    total = sum(s.quantity for s in total_result.scalars().all())
    product.stock = total

    await session.commit()
    await message.answer(
        f"Остаток обновлён:\n"
        f"Товар: {product.name}\n"
        f"Филиал: {shop.name}\n"
        f"Количество: {qty}\n"
        f"Всего по всем филиалам: {total}"
    )


@router.message(F.text == "/post_channel")
async def cmd_post_channel(message: types.Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    if not settings.CHANNEL_ID:
        await message.answer("CHANNEL_ID не задан в .env")
        return
    if not settings.WEBAPP_URL:
        await message.answer("WEBAPP_URL не задан в .env")
        return

    try:
        await message.bot.send_message(
            chat_id=settings.CHANNEL_ID,
            text="<b>KINGSTORE</b>\n\nКаталог Apple-техники с актуальными ценами и наличием. Открывайте и оформляйте заказ прямо здесь!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📱 Открыть каталог", web_app=WebAppInfo(url=settings.WEBAPP_URL))],
                ]
            ),
        )
        await message.answer(f"Сообщение с Mini App отправлено в канал {settings.CHANNEL_ID}")
    except Exception as e:
        await message.answer(f"Ошибка отправки в канал: {e}\n\nУбедитесь, что бот добавлен в канал и является администратором.")
