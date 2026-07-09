import datetime

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.bot.states import OrderForm, RequestForm
from app.bot.keyboards import order_confirm_keyboard, request_confirm_keyboard, shop_select_keyboard
from app.bot.handlers.client import get_or_create_user
from app.bot.handlers.cart import get_user_cart, cart_text
from app.models import Order, OrderItem, OrderStatus, SyncStatus, Product, Shop
from app.services.livesklad import create_livesklad_order
from app.services.notifications import notify_admins_new_order, notify_user_order_status

router = Router()


@router.callback_query(F.data == "checkout")
async def checkout(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await get_or_create_user(session, callback.message)
    cart = await get_user_cart(session, user.id)
    if not cart.items:
        await callback.answer("Корзина пуста")
        return
    await state.set_state(OrderForm.name)
    await callback.message.answer("Введите ваше имя:")


@router.message(OrderForm.name)
async def order_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(OrderForm.phone)
    await message.answer(
        "Введите номер телефона или нажмите кнопку ниже:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


@router.message(OrderForm.phone, F.contact)
async def order_phone_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await state.set_state(OrderForm.city)
    await message.answer("Введите ваш город:", reply_markup=types.ReplyKeyboardRemove())


@router.message(OrderForm.phone)
async def order_phone_text(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderForm.city)
    await message.answer("Введите ваш город:")


@router.message(OrderForm.city)
async def order_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(OrderForm.delivery)
    await message.answer(
        "Выберите способ получения:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Самовывоз")],
                [types.KeyboardButton(text="Доставка по городу")],
                [types.KeyboardButton(text="Доставка почтой/курьером")],
                [types.KeyboardButton(text="Индивидуальное согласование")],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


@router.message(OrderForm.delivery)
async def order_delivery(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.update_data(delivery=message.text)
    result = await session.execute(select(Shop).where(Shop.is_active == True))
    shops = result.scalars().all()
    if not shops:
        await state.set_state(OrderForm.comment)
        await message.answer("Добавьте комментарий к заказу (или отправьте '-', если не нужен):", reply_markup=types.ReplyKeyboardRemove())
        return
    await state.set_state(OrderForm.shop)
    await message.answer("Выберите удобный филиал для бронирования:", reply_markup=shop_select_keyboard(shops))


@router.callback_query(F.data.startswith("shop:"), OrderForm.shop)
async def order_shop(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    shop_id = int(callback.data.split(":", 1)[1])
    await state.update_data(shop_id=shop_id)
    await state.set_state(OrderForm.comment)
    await callback.message.edit_text("Добавьте комментарий к заказу (или отправьте '-', если не нужен):")


@router.message(OrderForm.comment)
async def order_comment(message: types.Message, state: FSMContext, session: AsyncSession):
    comment = message.text if message.text != "-" else ""
    data = await state.update_data(comment=comment)
    user = await get_or_create_user(session, message)
    cart = await get_user_cart(session, user.id)

    await state.set_state(OrderForm.confirm)

    shop_name = "Не выбран"
    shop_id = data.get("shop_id")
    if shop_id:
        shop_result = await session.execute(select(Shop).where(Shop.id == shop_id))
        shop = shop_result.scalar_one_or_none()
        if shop:
            shop_name = shop.name

    text = await cart_text(session, cart)
    text += (
        f"\n\n<b>Контактные данные:</b>\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Город: {data['city']}\n"
        f"Способ получения: {data['delivery']}\n"
        f"Филиал: {shop_name}\n"
    )
    if comment:
        text += f"Комментарий: {comment}\n"

    await message.answer(text, reply_markup=order_confirm_keyboard())


@router.callback_query(F.data == "confirm_order", OrderForm.confirm)
async def confirm_order(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user = await get_or_create_user(session, callback.message)
    cart = await get_user_cart(session, user.id)

    if not cart.items:
        await callback.answer("Корзина пуста")
        return

    # Recalculate prices
    total = 0
    for item in cart.items:
        product = item.product
        item.price_snapshot = product.price
        item_total = product.price * item.quantity
        total += item_total

    order_number = f"KS-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    order = Order(
        order_number=order_number,
        user_id=user.id,
        shop_id=data.get("shop_id"),
        status=OrderStatus.NEW,
        total_amount=total,
        delivery_type=data["delivery"],
        customer_name=data["name"],
        customer_phone=data["phone"],
        customer_city=data["city"],
        comment=data.get("comment", ""),
        sync_status=SyncStatus.PENDING,
    )
    order.user = user
    session.add(order)
    await session.flush()

    for item in cart.items:
        product = item.product
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            quantity=item.quantity,
            price=item.price_snapshot,
            total=item.price_snapshot * item.quantity,
        )
        session.add(order_item)
        order.items.append(order_item)

    for item in cart.items:
        await session.delete(item)
    await session.commit()

    # Load shop relationship for LiveSklad sync
    if order.shop_id:
        shop_result = await session.execute(select(Shop).where(Shop.id == order.shop_id))
        order.shop = shop_result.scalar_one_or_none()

    # Send to LiveSklad
    livesklad_id = None
    try:
        livesklad_id = await create_livesklad_order(order)
        order.livesklad_order_id = livesklad_id
        order.sync_status = SyncStatus.SUCCESS
        await session.commit()
    except Exception as e:
        order.status = OrderStatus.PENDING_SYNC
        order.sync_status = SyncStatus.ERROR
        order.sync_message = str(e)
        await session.commit()
        await notify_admins_new_order(callback.message.bot, order, error=str(e))

    await notify_user_order_status(callback.message.bot, user.telegram_id, order)
    if order.sync_status == SyncStatus.SUCCESS:
        await notify_admins_new_order(callback.message.bot, order)

    await state.clear()
    await callback.message.edit_text(
        f"Ваш заказ <b>#{order_number}</b> принят!\n\n"
        f"Сумма: {total} ₽\n"
        f"Статус: {order.status.value}\n\n"
        "Мы сообщим, когда заказ будет обработан."
    )


@router.callback_query(F.data == "cancel_order", OrderForm.confirm)
async def cancel_order(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Оформление заказа отменено.")


@router.callback_query(F.data == "edit_order", OrderForm.confirm)
async def edit_order(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderForm.name)
    await callback.message.answer("Введите ваше имя:")


# Direct request form from product card (KingStore style)
@router.callback_query(F.data.startswith("order:"))
async def request_product(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    product_id = int(callback.data.split(":", 1)[1])
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        await callback.answer("Товар не найден")
        return

    await state.set_state(RequestForm.name)
    await state.update_data(product_id=product_id, product_name=product.name)
    await callback.message.answer(
        "<b>Подтвердите заявку</b>\n\n"
        "После оформления заявки менеджер свяжется с вами в течение 5 минут в рабочее время.\n\n"
        "Введите ваше имя:",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.message(RequestForm.name)
async def request_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(RequestForm.phone)
    await message.answer(
        "Введите номер телефона или поделитесь контактом:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


@router.message(RequestForm.phone, F.contact)
async def request_phone_contact(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.update_data(phone=message.contact.phone_number)
    await _show_request_shop(message, state, session)


@router.message(RequestForm.phone)
async def request_phone_text(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.update_data(phone=message.text)
    await _show_request_shop(message, state, session)


async def _show_request_shop(message: types.Message, state: FSMContext, session: AsyncSession):
    result = await session.execute(select(Shop).where(Shop.is_active == True))
    shops = result.scalars().all()
    if not shops:
        await _show_request_confirm(message, state, session)
        return
    await state.set_state(RequestForm.shop)
    await message.answer("Выберите удобный филиал для бронирования:", reply_markup=shop_select_keyboard(shops))


@router.callback_query(F.data.startswith("shop:"), RequestForm.shop)
async def request_shop(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    shop_id = int(callback.data.split(":", 1)[1])
    await state.update_data(shop_id=shop_id)
    await _show_request_confirm_from_callback(callback, state, session)


async def _show_request_confirm(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.set_state(RequestForm.confirm)
    source = data.get("source", "product")
    if source == "best_price":
        subject = "Узнать лучшую цену"
    elif source == "contact_manager":
        subject = "Вопрос менеджеру"
    else:
        subject = data.get('product_name', 'Товар')

    shop_name = "Не выбран"
    shop_id = data.get("shop_id")
    if shop_id:
        shop_result = await session.execute(select(Shop).where(Shop.id == shop_id))
        shop = shop_result.scalar_one_or_none()
        if shop:
            shop_name = shop.name

    text = (
        f"<b>Подтвердите заявку</b>\n\n"
        f"После оформления заявки менеджер свяжется с вами в течение 5 минут в рабочее время.\n\n"
        f"Тема: {subject}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Филиал: {shop_name}\n"
    )
    await message.answer(text, reply_markup=request_confirm_keyboard())


async def _show_request_confirm_from_callback(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.set_state(RequestForm.confirm)
    source = data.get("source", "product")
    if source == "best_price":
        subject = "Узнать лучшую цену"
    elif source == "contact_manager":
        subject = "Вопрос менеджеру"
    else:
        subject = data.get('product_name', 'Товар')

    shop_name = "Не выбран"
    shop_id = data.get("shop_id")
    if shop_id:
        shop_result = await session.execute(select(Shop).where(Shop.id == shop_id))
        shop = shop_result.scalar_one_or_none()
        if shop:
            shop_name = shop.name

    text = (
        f"<b>Подтвердите заявку</b>\n\n"
        f"После оформления заявки менеджер свяжется с вами в течение 5 минут в рабочее время.\n\n"
        f"Тема: {subject}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Филиал: {shop_name}\n"
    )
    await callback.message.edit_text(text, reply_markup=request_confirm_keyboard())


@router.callback_query(F.data == "send_request", RequestForm.confirm)
async def send_request(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user = await get_or_create_user(session, callback.message)
    product_id = data.get("product_id")
    source = data.get("source", "product")
    product = None
    if product_id:
        stmt = select(Product).where(Product.id == product_id)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()

    total = product.price if product else 0
    order_number = f"KS-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    if source == "best_price":
        delivery_type = "Узнать лучшую цену"
        comment = "Клиент хочет узнать лучшую цену"
    elif source == "contact_manager":
        delivery_type = "Вопрос менеджеру"
        comment = data.get("question", "Клиент написал менеджеру")
    else:
        delivery_type = "Заявка на товар"
        comment = f"Заявка на товар: {data.get('product_name', '-')}"

    order = Order(
        order_number=order_number,
        user_id=user.id,
        shop_id=data.get("shop_id"),
        status=OrderStatus.NEW,
        total_amount=total,
        delivery_type=delivery_type,
        customer_name=data["name"],
        customer_phone=data["phone"],
        comment=comment,
        sync_status=SyncStatus.PENDING,
    )
    order.user = user
    session.add(order)
    await session.flush()

    if product:
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            quantity=1,
            price=product.price,
            total=product.price,
        )
        session.add(order_item)
        order.items.append(order_item)

    await session.commit()

    if order.shop_id:
        shop_result = await session.execute(select(Shop).where(Shop.id == order.shop_id))
        order.shop = shop_result.scalar_one_or_none()

    try:
        livesklad_id = await create_livesklad_order(order)
        order.livesklad_order_id = livesklad_id
        order.sync_status = SyncStatus.SUCCESS
        await session.commit()
    except Exception as e:
        order.status = OrderStatus.PENDING_SYNC
        order.sync_status = SyncStatus.ERROR
        order.sync_message = str(e)
        await session.commit()
        await notify_admins_new_order(callback.message.bot, order, error=str(e))

    await notify_user_order_status(callback.message.bot, user.telegram_id, order)
    if order.sync_status == SyncStatus.SUCCESS:
        await notify_admins_new_order(callback.message.bot, order)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Заявка <b>#{order_number}</b> отправлена!\n\n"
        f"Менеджер свяжется с вами в течение 5 минут в рабочее время."
    )


@router.callback_query(F.data == "edit_request", RequestForm.confirm)
async def edit_request(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(RequestForm.name)
    await callback.message.answer("Введите ваше имя:")


@router.callback_query(F.data == "cancel_request", RequestForm.confirm)
async def cancel_request(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Заявка отменена.")
