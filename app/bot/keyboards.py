from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from app.config import settings


MAIN_MENU_CLIENT = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🔎 Поиск")],
        [KeyboardButton(text="🔄 Trade-in"), KeyboardButton(text="🎁 Розыгрыши")],
        [KeyboardButton(text="💰 Узнать лучшую цену"), KeyboardButton(text="💬 Написать менеджеру")],
        [KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="📦 Мои заказы")],
    ],
    resize_keyboard=True,
)


MAIN_MENU_ADMIN = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Новые заявки"), KeyboardButton(text="🔄 Trade-in заявки")],
        [KeyboardButton(text="🎁 Розыгрыши"), KeyboardButton(text="🔄 Синхронизация")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🚨 Ошибки")],
    ],
    resize_keyboard=True,
)


def main_menu_inline():
    buttons = [
        [InlineKeyboardButton(text="🛍 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🔄 Trade-in", callback_data="tradein")],
        [InlineKeyboardButton(text="🎁 Розыгрыши", callback_data="giveaways")],
        [InlineKeyboardButton(text="💰 Узнать лучшую цену", callback_data="best_price")],
        [InlineKeyboardButton(text="💬 Написать менеджеру", callback_data="contact_manager")],
    ]
    if settings.WEBAPP_URL:
        buttons.append([InlineKeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=settings.WEBAPP_URL))])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def catalog_menu(categories):
    buttons = [
        [InlineKeyboardButton(text=f"{cat}", callback_data=f"category:{cat}")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text="🔍 Поиск по товарам", callback_data="search")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def category_products_keyboard(products):
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(text=p.name, callback_data=f"product:{p.id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_card_keyboard(product_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Заказать", callback_data=f"order:{product_id}")],
            [InlineKeyboardButton(text="❓ Задать вопрос", callback_data=f"ask:{product_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_category")],
        ]
    )


def product_specs_keyboard(product_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Заказать", callback_data=f"order:{product_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"product:{product_id}")],
        ]
    )


def request_confirm_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📨 Отправить заявку", callback_data="send_request")],
            [InlineKeyboardButton(text="✏️ Изменить данные", callback_data="edit_request")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_request")],
        ]
    )



def order_confirm_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="confirm_order")],
            [InlineKeyboardButton(text="✏️ Изменить данные", callback_data="edit_order")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_order")],
        ]
    )


def tradein_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 iPhone", callback_data="tradein_type:iPhone")],
            [InlineKeyboardButton(text="📱 iPad", callback_data="tradein_type:iPad")],
            [InlineKeyboardButton(text="⌚ Apple Watch", callback_data="tradein_type:Apple Watch")],
            [InlineKeyboardButton(text="🎧 AirPods", callback_data="tradein_type:AirPods")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ]
    )


def tradein_confirm_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="tradein_confirm")],
            [InlineKeyboardButton(text="✏️ Изменить", callback_data="tradein_edit")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="tradein_cancel")],
        ]
    )


def giveaways_menu(active_giveaways):
    buttons = []
    for g in active_giveaways:
        buttons.append([InlineKeyboardButton(text=g.title, callback_data=f"giveaway:{g.id}")])
    buttons.append([InlineKeyboardButton(text="🏆 Результаты розыгрышей", callback_data="giveaway_results")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def giveaway_action_keyboard(giveaway_id: int, channel_url: str | None):
    buttons = [
        [InlineKeyboardButton(text="🎟 Участвовать", callback_data=f"giveaway_join:{giveaway_id}")],
        [InlineKeyboardButton(text="👥 Пригласить участника", callback_data=f"giveaway_invite:{giveaway_id}")],
    ]
    if channel_url:
        buttons.append([InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_url)])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="giveaways")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cart_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
            [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
            [InlineKeyboardButton(text="🔙 В каталог", callback_data="catalog")],
        ]
    )



def shop_select_keyboard(shops):
    buttons = []
    for shop in shops:
        buttons.append([InlineKeyboardButton(text=shop.name, callback_data=f"shop:{shop.id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_request_keyboard(request_id: int, livesklad_id: str | None):
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm:{request_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_cancel:{request_id}")],
        [InlineKeyboardButton(text="💬 Связаться", callback_data=f"admin_contact:{request_id}")],
    ]
    if livesklad_id:
        buttons.append([InlineKeyboardButton(text="🔗 Открыть в LiveSklad", url=f"https://livesklad.com/orders/{livesklad_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🔄 Повторить синхронизацию", callback_data=f"admin_resync:{request_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_tradein_keyboard(tradein_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Обработано", callback_data=f"admin_tradein_process:{tradein_id}")],
            [InlineKeyboardButton(text="💬 Связаться", callback_data=f"admin_tradein_contact:{tradein_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_tradein_cancel:{tradein_id}")],
        ]
    )
