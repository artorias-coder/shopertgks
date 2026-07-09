import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states import TradeInForm
from app.bot.keyboards import tradein_menu_keyboard, tradein_confirm_keyboard
from app.bot.handlers.client import get_or_create_user
from app.models import TradeIn, TradeInStatus
from app.services.notifications import notify_admins_tradein
from app.services.livesklad import create_livesklad_tradein

router = Router()


@router.message(F.text == "🔄 Trade-in")
async def tradein_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "<b>Trade-in</b>\n\n"
        "Обменяйте старое устройство на новое с выгодой до 80.000 ₽.\n"
        "Оценка за 1 минуту. Выберите тип устройства:",
        reply_markup=tradein_menu_keyboard(),
    )


@router.callback_query(F.data == "tradein")
async def tradein_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "<b>Trade-in</b>\n\n"
        "Обменяйте старое устройство на новое с выгодой до 80.000 ₽.\n"
        "Оценка за 1 минуту. Выберите тип устройства:",
        reply_markup=tradein_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("tradein_type:"))
async def tradein_type(callback: types.CallbackQuery, state: FSMContext):
    device_type = callback.data.split(":", 1)[1]
    await state.update_data(device_type=device_type)
    await state.set_state(TradeInForm.model)
    await callback.message.edit_text(f"Введите модель {device_type}:")


@router.message(TradeInForm.model)
async def tradein_model(message: types.Message, state: FSMContext):
    await state.update_data(model=message.text)
    await state.set_state(TradeInForm.battery)
    await message.answer(
        "Оцените состояние батареи:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Отличное (90-100%)", callback_data="battery:excellent")],
                [types.InlineKeyboardButton(text="Хорошее (80-89%)", callback_data="battery:good")],
                [types.InlineKeyboardButton(text="Удовлетворительное (70-79%)", callback_data="battery:fair")],
                [types.InlineKeyboardButton(text="Ниже 70%", callback_data="battery:poor")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("battery:"))
async def tradein_battery(callback: types.CallbackQuery, state: FSMContext):
    battery = callback.data.split(":", 1)[1]
    battery_map = {
        "excellent": "Отличное (90-100%)",
        "good": "Хорошее (80-89%)",
        "fair": "Удовлетворительное (70-79%)",
        "poor": "Ниже 70%",
    }
    await state.update_data(battery=battery_map.get(battery, battery))
    await state.set_state(TradeInForm.condition)
    await callback.message.edit_text(
        "Оцените состояние устройства:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Как новое", callback_data="condition:like_new")],
                [types.InlineKeyboardButton(text="Отличное", callback_data="condition:excellent")],
                [types.InlineKeyboardButton(text="Хорошее", callback_data="condition:good")],
                [types.InlineKeyboardButton(text="Есть мелкие следы использования", callback_data="condition:fair")],
                [types.InlineKeyboardButton(text="Повреждения", callback_data="condition:poor")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("condition:"))
async def tradein_condition(callback: types.CallbackQuery, state: FSMContext):
    condition = callback.data.split(":", 1)[1]
    condition_map = {
        "like_new": "Как новое",
        "excellent": "Отличное",
        "good": "Хорошее",
        "fair": "Есть мелкие следы использования",
        "poor": "Повреждения",
    }
    await state.update_data(condition=condition_map.get(condition, condition))
    data = await state.get_data()
    await state.set_state(TradeInForm.confirm)

    text = (
        f"<b>Подтвердите данные Trade-in</b>\n\n"
        f"Тип устройства: {data['device_type']}\n"
        f"Модель: {data['model']}\n"
        f"Состояние батареи: {data['battery']}\n"
        f"Состояние устройства: {data['condition']}\n\n"
        "После подтверждения менеджер свяжется с вами в течение 5 минут в рабочее время."
    )
    await callback.message.edit_text(text, reply_markup=tradein_confirm_keyboard())


@router.callback_query(F.data == "tradein_confirm")
async def tradein_confirm(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user = await get_or_create_user(session, callback.message)

    tradein = TradeIn(
        user_id=user.id,
        device_type=data["device_type"],
        model=data["model"],
        battery_condition=data["battery"],
        device_condition=data["condition"],
        status=TradeInStatus.NEW,
    )
    session.add(tradein)
    await session.commit()

    # Refresh to load user relationship
    await session.refresh(tradein)

    try:
        livesklad_id = await create_livesklad_tradein(tradein)
        tradein.livesklad_id = livesklad_id
        await session.commit()
    except Exception:
        # Store error but keep trade-in new; admin will retry manually
        logging.exception("Failed to sync trade-in %s to LiveSklad", tradein.id)

    await notify_admins_tradein(callback.message.bot, tradein)
    await state.clear()

    await callback.message.edit_text(
        "✅ Заявка на Trade-in отправлена!\n\n"
        "Менеджер свяжется с вами в течение 5 минут в рабочее время."
    )


@router.callback_query(F.data == "tradein_edit")
async def tradein_edit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TradeInForm.device_type)
    await callback.message.edit_text(
        "Выберите тип устройства:",
        reply_markup=tradein_menu_keyboard(),
    )


@router.callback_query(F.data == "tradein_cancel")
async def tradein_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Заявка на Trade-in отменена.")
