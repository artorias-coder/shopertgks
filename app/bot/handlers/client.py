from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.bot.keyboards import MAIN_MENU_CLIENT, MAIN_MENU_ADMIN, main_menu_inline
from app.bot.states import SupportState, RequestForm
from app.models import User, UserRole
from app.config import settings

router = Router()


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids or telegram_id == settings.superadmin_id


async def get_or_create_user(session: AsyncSession, message: types.Message) -> User:
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        role = UserRole.SUPERADMIN if message.from_user.id == settings.superadmin_id else UserRole.CLIENT
        if message.from_user.id in settings.admin_ids:
            role = UserRole.ADMIN
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            name=message.from_user.full_name,
            role=role,
        )
        session.add(user)
        await session.commit()
    return user


@router.message(F.text == "/start")
async def cmd_start(message: types.Message, session: AsyncSession):
    user = await get_or_create_user(session, message)
    if user.role in (UserRole.ADMIN, UserRole.SUPERADMIN):
        await message.answer("Добро пожаловать в админ-панель KingStore!", reply_markup=MAIN_MENU_ADMIN)
    else:
        await message.answer(
            "<b>Добро пожаловать в KingStore!</b>\n\n"
            "Официальный бот магазина Apple-техники.\n"
            "Выберите раздел или напишите менеджеру:",
            reply_markup=main_menu_inline(),
        )


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "<b>Главное меню</b>\n\n"
        "Официальный бот магазина Apple-техники.\n"
        "Выберите раздел:",
        reply_markup=main_menu_inline(),
    )


@router.message(F.text == "💰 Узнать лучшую цену")
async def best_price(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.set_state(RequestForm.name)
    await state.update_data(source="best_price")
    await message.answer(
        "Оставьте заявку — менеджер ответит за 2–5 минут и подберёт лучшую цену.\n\n"
        "Введите ваше имя:",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.message(F.text == "💬 Написать менеджеру")
async def contact_manager(message: types.Message, state: FSMContext):
    await state.set_state(SupportState.question)
    await message.answer("Опишите ваш вопрос. Менеджер скоро свяжется с вами в рабочее время.")


@router.message(F.text == "🎁 Акции")
async def promotions(message: types.Message):
    await message.answer("Актуальные акции появятся здесь. Следите за обновлениями!")


@router.message(F.text == "/webapp")
async def cmd_webapp(message: types.Message):
    if not settings.WEBAPP_URL:
        await message.answer("Mini App ещё не настроен. Укажите WEBAPP_URL в .env")
        return
    await message.answer(
        "Откройте каталог товаров через Mini App:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="📱 Открыть Mini App", web_app=types.WebAppInfo(url=settings.WEBAPP_URL))],
            ]
        ),
    )
