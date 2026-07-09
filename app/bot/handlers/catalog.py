from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.bot.keyboards import catalog_menu, category_products_keyboard, product_card_keyboard, product_specs_keyboard
from app.bot.states import SearchState
from app.models import Product, ProductStatus

router = Router()


@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: types.Message, session: AsyncSession):
    stmt = select(Product.category).where(
        Product.status == ProductStatus.ACTIVE
    ).group_by(Product.category).order_by(Product.category)
    result = await session.execute(stmt)
    categories = [r for r in result.scalars().all() if r]

    if not categories:
        await message.answer("Каталог пока пуст. Синхронизация с Google Sheets ещё не выполнена.")
        return

    await message.answer(
        "<b>Каталог</b>\n\n🔍 Поиск по товарам\n\nВыберите категорию:",
        reply_markup=catalog_menu(categories),
    )


@router.callback_query(F.data == "catalog")
async def show_catalog_callback(callback: types.CallbackQuery, session: AsyncSession):
    stmt = select(Product.category).where(
        Product.status == ProductStatus.ACTIVE
    ).group_by(Product.category).order_by(Product.category)
    result = await session.execute(stmt)
    categories = [r for r in result.scalars().all() if r]

    if not categories:
        await callback.answer("Каталог пока пуст")
        return

    await callback.message.edit_text(
        "<b>Каталог</b>\n\n🔍 Поиск по товарам\n\nВыберите категорию:",
        reply_markup=catalog_menu(categories),
    )


@router.callback_query(F.data.startswith("category:"))
async def show_category(callback: types.CallbackQuery, session: AsyncSession):
    category = callback.data.split(":", 1)[1]
    stmt = select(Product).where(
        Product.category == category,
        Product.status == ProductStatus.ACTIVE,
    ).order_by(Product.name)
    result = await session.execute(stmt)
    products = result.scalars().all()

    if not products:
        await callback.answer("В этой категории пока нет товаров")
        return

    await callback.message.edit_text(
        f"<b>{category}</b>\n\nВыберите товар:",
        reply_markup=category_products_keyboard(products),
    )


@router.callback_query(F.data.startswith("product:"))
async def show_product(callback: types.CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":", 1)[1])
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        await callback.answer("Товар не найден")
        return

    stock_text = f"В наличии: {product.stock} шт." if product.stock > 0 else "Нет в наличии"
    price_text = f"Стоимость: <b>{product.price} ₽</b>"
    if product.old_price:
        price_text = f"Стоимость: <s>{product.old_price} ₽</s>\nСтоимость по акции: <b>{product.price} ₽</b>"

    caption = (
        f"<b>{product.name}</b>\n\n"
        f"{price_text}\n"
        f"{stock_text}\n\n"
        f"{product.description or ''}"
    )

    if product.photo_url:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=product.photo_url,
            caption=caption,
            reply_markup=product_card_keyboard(product.id),
        )
    else:
        await callback.message.edit_text(
            caption,
            reply_markup=product_card_keyboard(product.id),
        )


@router.callback_query(F.data == "back_to_category")
async def back_to_category(callback: types.CallbackQuery, session: AsyncSession):
    # Try to infer category from current product; fallback to catalog
    await show_catalog_callback(callback, session)


@router.callback_query(F.data.startswith("specs:"))
async def show_specs(callback: types.CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":", 1)[1])
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        await callback.answer("Товар не найден")
        return

    text = f"<b>Характеристики: {product.name}</b>\n\n{product.description or 'Характеристики появятся позже.'}"
    await callback.message.edit_text(text, reply_markup=product_specs_keyboard(product.id))


@router.message(F.text == "🔎 Поиск")
@router.callback_query(F.data == "search")
async def search_start(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.query)
    text = "🔍 Введите название товара, модель или артикул для поиска:"
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text)
    else:
        await event.answer(text)


@router.message(SearchState.query)
async def search_query(message: types.Message, state: FSMContext, session: AsyncSession):
    query = message.text.strip().lower()
    await state.clear()

    stmt = select(Product).where(
        Product.status == ProductStatus.ACTIVE,
        or_(
            func.lower(Product.name).contains(query),
            func.lower(Product.sku).contains(query),
            func.lower(Product.category).contains(query),
            func.lower(Product.description).contains(query),
        ),
    ).limit(20)
    result = await session.execute(stmt)
    products = result.scalars().all()

    if not products:
        await message.answer(
            "Не нашёл такой товар. Хотите отправить запрос менеджеру?",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="💬 Написать менеджеру", callback_data="contact_manager")],
                    [types.InlineKeyboardButton(text="🔙 В каталог", callback_data="catalog")],
                ]
            ),
        )
        return

    await message.answer(
        f"Результаты поиска по «{query}»:",
        reply_markup=category_products_keyboard(products),
    )


@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "<b>Главное меню</b>\n\n"
        "Официальный бот магазина Apple-техники.\n"
        "Выберите раздел:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[]),
    )
