from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.google_sheets import sync_products
from app.services.livesklad import create_livesklad_order
from app.models import Order, OrderStatus, SyncStatus
from app.services.notifications import notify_user_order_status


celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "sync-google-sheets": {
            "task": "app.tasks.sync_google_sheets",
            "schedule": settings.GOOGLE_SYNC_INTERVAL_MINUTES * 60,
        },
        "retry-livesklad": {
            "task": "app.tasks.retry_livesklad_orders",
            "schedule": 300,
        },
    },
)


@celery_app.task
def sync_google_sheets():
    import asyncio
    asyncio.run(_sync_google_sheets())


async def _sync_google_sheets():
    async with AsyncSessionLocal() as session:
        await sync_products(session)


@celery_app.task
def retry_livesklad_orders():
    import asyncio
    asyncio.run(_retry_livesklad_orders())


async def _retry_livesklad_orders():
    async with AsyncSessionLocal() as session:
        stmt = select(Order).where(Order.status == OrderStatus.PENDING_SYNC).limit(10)
        result = await session.execute(stmt)
        orders = result.scalars().all()
        for order in orders:
            try:
                livesklad_id = await create_livesklad_order(order)
                order.livesklad_order_id = livesklad_id
                order.status = OrderStatus.NEW
                order.sync_status = SyncStatus.SUCCESS
                # Notify user would need bot instance; skip here or send via API
            except Exception as e:
                order.sync_message = str(e)
            await session.commit()
