from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.bot.keyboards import giveaways_menu, giveaway_action_keyboard
from app.bot.handlers.client import get_or_create_user
from app.models import Giveaway, GiveawayStatus, GiveawayParticipant

router = Router()


@router.message(F.text == "🎁 Розыгрыши")
async def giveaways_start(message: types.Message, session: AsyncSession):
    stmt = select(Giveaway).where(Giveaway.status == GiveawayStatus.ACTIVE).order_by(desc(Giveaway.created_at))
    result = await session.execute(stmt)
    active = result.scalars().all()

    if not active:
        await message.answer(
            "<b>Розыгрыши</b>\n\n"
            "Сейчас нет активных розыгрышей.\n"
            "Следите за обновлениями — разыгрываем iPhone, авто и другие призы!",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏆 Результаты розыгрышей", callback_data="giveaway_results")],
                    [types.InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
                ]
            ),
        )
        return

    await message.answer(
        "<b>Розыгрыши</b>\n\n"
        "Главный приз — автомобиль!\n"
        "Чтобы участвовать, подпишись на Telegram-канал и нажми «Участвовать».\n"
        "Победителя объявим публично в канале.",
        reply_markup=giveaways_menu(active),
    )


@router.callback_query(F.data == "giveaways")
async def giveaways_callback(callback: types.CallbackQuery, session: AsyncSession):
    stmt = select(Giveaway).where(Giveaway.status == GiveawayStatus.ACTIVE).order_by(desc(Giveaway.created_at))
    result = await session.execute(stmt)
    active = result.scalars().all()

    if not active:
        await callback.message.edit_text(
            "Сейчас нет активных розыгрышей.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏆 Результаты розыгрышей", callback_data="giveaway_results")],
                    [types.InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
                ]
            ),
        )
        return

    await callback.message.edit_text(
        "<b>Розыгрыши</b>\n\n"
        "Главный приз — автомобиль!\n"
        "Чтобы участвовать, подпишись на Telegram-канал и нажми «Участвовать».\n"
        "Победителя объявим публично в канале.",
        reply_markup=giveaways_menu(active),
    )


@router.callback_query(F.data.startswith("giveaway:"))
async def giveaway_detail(callback: types.CallbackQuery, session: AsyncSession):
    giveaway_id = int(callback.data.split(":", 1)[1])
    stmt = select(Giveaway).where(Giveaway.id == giveaway_id)
    result = await session.execute(stmt)
    giveaway = result.scalar_one_or_none()
    if not giveaway:
        await callback.answer("Розыгрыш не найден")
        return

    text = (
        f"<b>{giveaway.title}</b>\n\n"
        f"{giveaway.description or ''}\n\n"
        f"Главный приз: {giveaway.prize or 'автомобиль'}"
    )
    await callback.message.edit_text(text, reply_markup=giveaway_action_keyboard(giveaway.id, giveaway.channel_url))


@router.callback_query(F.data.startswith("giveaway_join:"))
async def giveaway_join(callback: types.CallbackQuery, session: AsyncSession):
    giveaway_id = int(callback.data.split(":", 1)[1])
    user = await get_or_create_user(session, callback.message)

    stmt = select(GiveawayParticipant).where(
        GiveawayParticipant.giveaway_id == giveaway_id,
        GiveawayParticipant.user_id == user.id,
    )
    result = await session.execute(stmt)
    participant = result.scalar_one_or_none()

    if participant:
        await callback.answer("Вы уже участвуете в этом розыгрыше")
        return

    participant = GiveawayParticipant(giveaway_id=giveaway_id, user_id=user.id)
    session.add(participant)
    await session.commit()

    await callback.answer("Вы участвуете!")
    await callback.message.edit_text(
        "✅ Вы участвуете в розыгрыше!\n\n"
        "Приглашайте друзей — больше друзей, больше шансов выиграть!",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="👥 Пригласить участника", callback_data=f"giveaway_invite:{giveaway_id}")],
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="giveaways")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("giveaway_invite:"))
async def giveaway_invite(callback: types.CallbackQuery, session: AsyncSession):
    giveaway_id = int(callback.data.split(":", 1)[1])
    user = await get_or_create_user(session, callback.message)

    stmt = select(GiveawayParticipant).where(
        GiveawayParticipant.giveaway_id == giveaway_id,
        GiveawayParticipant.user_id == user.id,
    )
    result = await session.execute(stmt)
    participant = result.scalar_one_or_none()

    if participant:
        participant.invited_count += 1
        participant.tickets += 1
        await session.commit()

    await callback.answer("Спасибо за приглашение!")
    await callback.message.edit_text(
        "👥 Приглашайте друзей по своей ссылке.\n\n"
        "Больше друзей — больше шансов выиграть!",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="giveaways")],
            ]
        ),
    )


@router.callback_query(F.data == "giveaway_results")
async def giveaway_results(callback: types.CallbackQuery, session: AsyncSession):
    stmt = select(Giveaway).where(Giveaway.status == GiveawayStatus.COMPLETED).order_by(desc(Giveaway.created_at)).limit(10)
    result = await session.execute(stmt)
    completed = result.scalars().all()

    if not completed:
        await callback.message.edit_text(
            "История завершённых розыгрышей пока пуста.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="🔙 Назад", callback_data="giveaways")],
                ]
            ),
        )
        return

    text = "<b>Результаты розыгрышей</b>\n\nИстория завершённых розыгрышей и список победителей:\n\n"
    for g in completed:
        text += f"• {g.title} — завершён {g.updated_at.strftime('%d.%m.%Y')}\n"

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="giveaways")],
            ]
        ),
    )
