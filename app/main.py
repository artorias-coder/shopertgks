from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import asyncio
import logging

from app.database import engine, AsyncSessionLocal
from app.models import Base
from app.api.routers import router as api_router
from app.admin_router import router as admin_router, UPLOADS_DIR
from app.config import settings

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"
INDEX_HTML = WEBAPP_DIR / "index.html"

bot = None
dp = None
_sync_task = None

app = FastAPI(title="KingStore API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(admin_router)

if UPLOADS_DIR.is_dir():
    app.mount("/webapp/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
else:
    logging.warning(f"{UPLOADS_DIR} недоступна — раздел /webapp/uploads не смонтирован")

app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")


@app.get("/")
async def root():
    return FileResponse(str(INDEX_HTML))


async def _seed_default_categories(session: AsyncSession):
    from app.models import Category
    result = await session.execute(select(Category))
    if result.scalars().first():
        return
    defaults = [
        {"name": "iPhone", "description": "Выбрать модель и цену", "icon_emoji": "📱", "tile_size": "medium", "sort_order": 10},
        {"name": "iPad", "description": "Для учёбы / чтения / работы", "icon_emoji": "📲", "tile_size": "medium", "sort_order": 20},
        {"name": "Mac", "description": "Подобрать под задачи", "icon_emoji": "💻", "tile_size": "medium", "sort_order": 30},
        {"name": "Apple Watch", "description": "Подобрать под стиль", "icon_emoji": "⌚", "tile_size": "medium", "sort_order": 40},
        {"name": "AirPods", "description": "Подобрать формат и цвет", "icon_emoji": "🎧", "tile_size": "medium", "sort_order": 50},
        {"name": "Наушники и аудио", "description": "Подобрать формат и цвет", "icon_emoji": "🎵", "tile_size": "medium", "sort_order": 60},
        {"name": "Смартфоны Samsung", "description": "Открыть каталог", "icon_emoji": "📱", "tile_size": "medium", "sort_order": 70},
    ]
    for d in defaults:
        session.add(Category(**d))
    await session.commit()
    logging.info("Default categories seeded")


async def _migrate_columns(conn):
    from sqlalchemy import text
    try:
        await conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS color VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS memory VARCHAR(50)"))
        await conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS specs JSONB"))
    except Exception as e:
        logging.warning(f"Product columns migration skipped: {e}")
    try:
        # Новое значение статуса товара (ON_REQUEST) в models.py не появляется
        # само в уже существующем нативном PG enum "productstatus" — без ALTER
        # TYPE любой запрос со значением 'on_request' падает с ошибкой
        # "invalid input value for enum", что ломало /api/products целиком.
        await conn.execute(text("ALTER TYPE productstatus ADD VALUE IF NOT EXISTS 'on_request'"))
    except Exception as e:
        logging.warning(f"ProductStatus enum migration skipped: {e}")
    try:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) UNIQUE NOT NULL,
                description TEXT,
                image_url VARCHAR(1000),
                icon_emoji VARCHAR(50),
                tile_size VARCHAR(20) DEFAULT 'medium' NOT NULL,
                sort_order INTEGER DEFAULT 0 NOT NULL,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            )
        """))
    except Exception as e:
        logging.warning(f"Categories table migration skipped: {e}")


async def _periodic_sync_loop():
    """Фоновая синхронизация каталога с Google Sheets по таймеру.

    Раньше синк запускался только один раз при старте процесса — данные
    обновлялись лишь после ручного рестарта контейнера. Теперь каталог
    подтягивается сам, без вмешательства.
    """
    from app.services.google_sheets import sync_products

    interval = max(1, settings.GOOGLE_SYNC_INTERVAL_MINUTES) * 60
    while True:
        await asyncio.sleep(interval)
        try:
            async with AsyncSessionLocal() as session:
                stats = await sync_products(session)
            logging.info(f"Google Sheets periodic sync: {stats}")
        except Exception as e:
            logging.error(f"Periodic Google Sheets sync failed: {e}")


@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if settings.is_sqlite:
                pass
            else:
                await _migrate_columns(conn)
        logging.info("Database tables created/verified")
    except Exception as e:
        logging.error(f"Database startup error: {e}")

    try:
        async with AsyncSessionLocal() as session:
            await _seed_default_categories(session)
    except Exception as e:
        logging.error(f"Category seeding error: {e}")

    if settings.GOOGLE_SHEETS_ID:
        # На хостингах без отдельного Celery-воркера (например, Bothost)
        # запланированная через .delay() синхронизация никогда не выполняется —
        # некому забрать задачу из очереди. Поэтому синхронизируем каталог с
        # Google Sheets прямо при каждом старте приложения, а дальше — по
        # таймеру в фоне (см. _periodic_sync_loop), чтобы данные обновлялись
        # сами, без ручного рестарта контейнера.
        try:
            from app.services.google_sheets import sync_products

            async with AsyncSessionLocal() as session:
                stats = await sync_products(session)
            logging.info(f"Google Sheets sync at startup: {stats}")
        except Exception as e:
            logging.error(f"Google Sheets sync at startup failed: {e}")

        global _sync_task
        _sync_task = asyncio.create_task(_periodic_sync_loop())

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
    global bot, _sync_task
    if _sync_task is not None:
        _sync_task.cancel()
    if bot is not None:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.session.close()
        except Exception as e:
            logging.warning(f"Ошибка при удалении webhook: {e}")


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
        return {"status": "ok", "database": "ok"}
    except Exception as e:
        logging.error(f"Health check DB error: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable") from e


@app.post("/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    global dp
    if dp is None:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    if not settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    from aiogram.types import Update

    data = await request.json()
    update = Update(**data)
    await dp.feed_update(update, bot=bot)
    return {"ok": True}
