import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states import SupportState
from app.bot.handlers.client import get_or_create_user
from app.config import settings

router = Router()


@router.message(F.text == "💬 Поддержка")
async def start_support(message: types.Message, state: FSMContext):
    await state.set_state(SupportState.question)
    await state.update_data(source="general")
    await message.answer("Опишите ваш вопрос или проблему. Мы передадим её менеджеру.")


@router.callback_query(F.data.startswith("ask:"))
async def ask_product(callback: types.CallbackQuery, state: FSMContext):
    product_id = callback.data.split(":", 1)[1]
    await state.set_state(SupportState.question)
    await state.update_data(source="product", product_id=product_id)
    await callback.message.answer("Опишите ваш вопрос по товару. Мы передадим его менеджеру.")


@router.message(F.text == "💬 Написать менеджеру")
@router.callback_query(F.data == "contact_manager")
async def contact_manager(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.question)
    text = "Оставьте заявку — менеджер скоро свяжется с вами в рабочее время."
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text)
    else:
        await event.answer(text)


@router.message(SupportState.question)
async def receive_support_question(message: types.Message, state: FSMContext, session: AsyncSession):
    user = await get_or_create_user(session, message)
    data = await state.get_data()
    await state.clear()

    source = data.get("source", "general")
    product_id = data.get("product_id")
    product_info = ""
    if source == "product" and product_id:
        product_info = f"\nПо товару ID: {product_id}\n"

    text = (
        f"<b>Новое обращение</b>\n\n"
        f"Клиент: {user.name or 'не указано'}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Username: @{user.username or '-'}\n"
        f"Тип: {source}{product_info}\n"
        f"Вопрос:\n{message.text}"
    )

    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_message(admin_id, text)
        except Exception:
            logging.exception("Failed to notify admin %s about support question", admin_id)

    await message.answer("Спасибо! Ваш вопрос отправлен менеджеру. Мы скоро ответим.")
