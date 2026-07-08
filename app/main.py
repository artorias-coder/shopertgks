from fastapi import FastAPI, Depends, Request, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database import get_db, engine
from app.models import Base
from app.api.routers import router as api_router
from app.config import settings

bot = None
dp = None

app = FastAPI(title="KingStore API")
app.include_router(api_router, prefix="/api")
app.mount("/webapp", StaticFiles(directory="app/webapp", html=True), name="webapp")


@app.get("/")
async def root():
    return FileResponse("app/webapp/index.html")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.WEBHOOK_URL and settings.BOT_TOKEN:
        try:
            from app.run_bot import get_bot_and_dispatcher, set_bot_menu_button

            global bot, dp
            bot, dp = await get_bot_and_dispatcher()
            await set_bot_menu_button(bot)
            await bot.set_webhook(
                url=settings.WEBHOOK_URL,
                secret_token=settings.WEBHOOK_SECRET,
                drop_pending_updates=True,
            )
            logging.info(f"Webhook установлен: {settings.WEBHOOK_URL}")
        except Exception as e:
            logging.error(f"Не удалось установить webhook: {e}")


@app.on_event("shutdown")
async def shutdown():
    global bot
    if bot is not None:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.session.close()
        except Exception as e:
            logging.warning(f"Ошибка при удалении webhook: {e}")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    global dp
    if dp is None:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    from aiogram.types import Update

    data = await request.json()
    update = Update(**data)
    await dp.feed_update(update, bot=bot)
    return {"ok": True}


@app.get("/orders")
async def list_orders(session: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models import Order
    result = await session.execute(select(Order))
    orders = result.scalars().all()
    return [{"id": o.id, "number": o.order_number, "status": o.status.value} for o in orders]
