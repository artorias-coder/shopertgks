from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.bot.keyboards import cart_keyboard
from app.models import Product, Cart, CartItem, ProductStatus
from app.bot.handlers.client import get_or_create_user

router = Router()


async def get_user_cart(session: AsyncSession, user_id: int) -> Cart:
    stmt = select(Cart).where(Cart.user_id == user_id)
    result = await session.execute(stmt)
    cart = result.scalar_one_or_none()
    if not cart:
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.commit()
    return cart


async def cart_text(session: AsyncSession, cart: Cart) -> str:
    if not cart.items:
        return "Ваша корзина пуста."
    lines = ["<b>Корзина</b>\n"]
    total = 0
    for item in cart.items:
        product = item.product
        price = item.price_snapshot or product.price
        item_total = price * item.quantity
        total += item_total
        lines.append(
            f"{product.name}\n"
            f"{item.quantity} шт. × {price} ₽ = {item_total} ₽"
        )
    lines.append(f"\n<b>Итого: {total} ₽</b>")
    return "\n".join(lines)


@router.message(F.text == "🛒 Корзина")
async def show_cart(message: types.Message, session: AsyncSession):
    user = await get_or_create_user(session, message)
    cart = await get_user_cart(session, user.id)
    text = await cart_text(session, cart)
    await message.answer(text, reply_markup=cart_keyboard())


@router.callback_query(F.data.startswith("add:"))
async def add_to_cart(callback: types.CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":", 1)[1])
    user = await get_or_create_user(session, callback.message)
    cart = await get_user_cart(session, user.id)

    stmt = select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()

    if item:
        item.quantity += 1
    else:
        product_stmt = select(Product).where(Product.id == product_id)
        product_result = await session.execute(product_stmt)
        product = product_result.scalar_one()
        item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=1,
            price_snapshot=product.price,
        )
        session.add(item)

    await session.commit()
    await callback.answer("Товар добавлен в корзину")
    await callback.message.edit_reply_markup(reply_markup=callback.message.reply_markup)


@router.callback_query(F.data.startswith("inc:"))
async def increase_quantity(callback: types.CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":", 1)[1])
    user = await get_or_create_user(session, callback.message)
    cart = await get_user_cart(session, user.id)
    stmt = select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if item:
        item.quantity += 1
        await session.commit()
    await callback.answer("Количество увеличено")


@router.callback_query(F.data.startswith("dec:"))
async def decrease_quantity(callback: types.CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":", 1)[1])
    user = await get_or_create_user(session, callback.message)
    cart = await get_user_cart(session, user.id)
    stmt = select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if item:
        if item.quantity > 1:
            item.quantity -= 1
        else:
            await session.delete(item)
        await session.commit()
    await callback.answer("Количество уменьшено")


@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, callback.message)
    cart = await get_user_cart(session, user.id)
    for item in cart.items:
        await session.delete(item)
    await session.commit()
    await callback.message.edit_text("Корзина очищена.", reply_markup=cart_keyboard())
