import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.config import settings
from app.bot.handlers import client, catalog, cart, order, admin, support, tradein, giveaways
from app.bot.middlewares import DbSessionMiddleware
from app.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)

    if settings.WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Каталог", web_app=WebAppInfo(url=settings.WEBAPP_URL))
            )
        except Exception as e:
            logging.warning(f"Не удалось установить меню Mini App: {e}")

    dp.message.middleware(DbSessionMiddleware(AsyncSessionLocal))
    dp.callback_query.middleware(DbSessionMiddleware(AsyncSessionLocal))

    dp.include_router(client.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(order.router)
    dp.include_router(tradein.router)
    dp.include_router(giveaways.router)
    dp.include_router(admin.router)
    dp.include_router(support.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
