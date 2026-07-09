import datetime
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.admin_router import _check_admin
from app.config import settings
from app.database import get_db
from app.models import Product, Order, OrderItem, OrderStatus, ProductStatus, Shop, ProductStock, SyncLog, SyncStatus, TradeIn, TradeInStatus, Giveaway, GiveawayParticipant, User
from app.services.livesklad import create_livesklad_order, create_livesklad_tradein
from app.services.notifications import notify_admins_new_order, notify_admins_tradein, notify_user_order_status
from app.services.telegram_webapp import get_validated_user_id, get_validated_user_name, validate_init_data
from app.services.google_sheets import sync_products


async def _get_bot():
    from app.main import bot
    return bot


def _telegram_user_name(x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data")) -> str | None:
    return get_validated_user_name(x_telegram_init_data or "")


async def _get_or_create_user(session: AsyncSession, telegram_id: int, name: str | None = None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, name=name, role="client")
        session.add(user)
        await session.flush()
    return user


def verify_telegram_init_data(x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data")):
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram init data")
    if not validate_init_data(x_telegram_init_data):
        raise HTTPException(status_code=403, detail="Invalid Telegram init data")


def verify_telegram_user(x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data")) -> int:
    telegram_id = get_validated_user_id(x_telegram_init_data or "")
    if telegram_id is None:
        raise HTTPException(status_code=403, detail="Invalid Telegram init data")
    return telegram_id

router = APIRouter()


@router.get("/me")
async def get_me(telegram_id: int = Depends(verify_telegram_user)):
    # Отдельная проверка на бэкенде, а не только скрытие кнопки на фронте —
    # telegram_id уже провалидирован по HMAC подписи initData, так что его
    # нельзя подделать со стороны клиента, в отличие от простого JS-флага.
    is_admin = telegram_id in settings.admin_ids or telegram_id == settings.superadmin_id
    return {"telegram_id": telegram_id, "is_admin": is_admin}


# Товары с ценой-кодом 1/2 из таблицы (нет в наличии / только по запросу)
# должны оставаться видимыми в каталоге — просто с меткой вместо цены.
# HIDDEN и ARCHIVED — единственные статусы, которые реально скрывают товар.
VISIBLE_PRODUCT_STATUSES = (ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK, ProductStatus.ON_REQUEST)


@router.get("/products")
async def list_products(category: str | None = None, session: AsyncSession = Depends(get_db)):
    stmt = select(Product).where(Product.status.in_(VISIBLE_PRODUCT_STATUSES))
    if category:
        stmt = stmt.where(Product.category == category)
    try:
        result = await session.execute(stmt.order_by(Product.name))
    except Exception as e:
        # Например, если на проде ещё не применилась миграция ALTER TYPE ...
        # ADD VALUE 'on_request' — тогда падает весь каталог. Лучше показать
        # хотя бы активные товары, чем отдать 500 и обрушить весь Mini App.
        logging.error(f"list_products broad query failed, falling back to ACTIVE only: {e}")
        await session.rollback()
        fallback_stmt = select(Product).where(Product.status == ProductStatus.ACTIVE)
        if category:
            fallback_stmt = fallback_stmt.where(Product.category == category)
        result = await session.execute(fallback_stmt.order_by(Product.name))
    products = result.scalars().all()
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "subcategory": p.subcategory,
            "color": p.color,
            "memory": p.memory,
            "price": float(p.price) if p.price else None,
            "old_price": float(p.old_price) if p.old_price else None,
            "discount": float(p.discount) if p.discount else None,
            "stock": p.stock,
            "photo_url": p.photo_url,
            "description": p.description,
            "status": p.status.value,
        }
        for p in products
    ]


@router.get("/products/{product_id}")
async def get_product(product_id: int, session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(Product).options(selectinload(Product.stocks).selectinload(ProductStock.shop)).where(Product.id == product_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    # Наличие по точкам администратор выставляет вручную в панели (см.
    # /admin/api/products) — у LiveSklad нет публичного метода "остатки по
    # складу", только мастерские/заказы/касса/корзина/продажи.
    stocks = [
        {"shop_id": s.shop_id, "shop_name": s.shop.name if s.shop else None, "quantity": s.quantity}
        for s in p.stocks
        if s.shop and s.shop.is_active
    ]
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "category": p.category,
        "subcategory": p.subcategory,
        "color": p.color,
        "memory": p.memory,
        "specs": p.specs,
        "price": float(p.price) if p.price else None,
        "old_price": float(p.old_price) if p.old_price else None,
        "discount": float(p.discount) if p.discount else None,
        "stock": p.stock,
        "stocks": stocks,
        "photo_url": p.photo_url,
        "description": p.description,
        "status": p.status.value,
    }


@router.get("/categories")
async def list_categories(session: AsyncSession = Depends(get_db)):
    from app.models import Category
    result = await session.execute(
        select(Category).where(Category.is_active == True).order_by(Category.sort_order, Category.name)
    )
    categories = result.scalars().all()
    if categories:
        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "image_url": c.image_url,
                "icon_emoji": c.icon_emoji,
                "tile_size": c.tile_size,
            }
            for c in categories
        ]
    # Fallback: derive from products
    try:
        result = await session.execute(
            select(Product.category)
            .where(Product.status.in_(VISIBLE_PRODUCT_STATUSES))
            .group_by(Product.category)
            .order_by(Product.category)
        )
    except Exception as e:
        logging.error(f"list_categories broad query failed, falling back to ACTIVE only: {e}")
        await session.rollback()
        result = await session.execute(
            select(Product.category)
            .where(Product.status == ProductStatus.ACTIVE)
            .group_by(Product.category)
            .order_by(Product.category)
        )
    return [{"id": None, "name": r, "description": None, "image_url": None, "icon_emoji": None, "tile_size": "medium"} for r in result.scalars().all() if r]


@router.get("/shops")
async def list_shops(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Shop).where(Shop.is_active == True))
    shops = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "address": s.address,
            "color": s.color,
            "livesklad_id": s.livesklad_id,
        }
        for s in shops
    ]


@router.get("/product-stock/{product_id}")
async def product_stock(product_id: int, session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(ProductStock, Shop)
        .join(Shop, ProductStock.shop_id == Shop.id)
        .where(ProductStock.product_id == product_id, Shop.is_active == True)
    )
    rows = result.all()
    return [
        {
            "shop_id": shop.id,
            "shop_name": shop.name,
            "quantity": stock.quantity,
        }
        for stock, shop in rows
    ]


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1, le=10)


class OrderCreate(BaseModel):
    telegram_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=5, max_length=30)
    city: str = Field(..., min_length=1, max_length=100)
    delivery: str = Field(..., min_length=1, max_length=50)
    shop_id: int = Field(..., ge=1)
    comment: str | None = Field(None, max_length=1000)
    items: list[OrderItemCreate] = Field(..., min_items=1, max_items=20)


@router.post("/orders")
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_db),
    _=Depends(verify_telegram_init_data),
):
    # find or create user
    result = await session.execute(select(User).where(User.telegram_id == payload.telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=payload.telegram_id,
            name=payload.name,
            phone=payload.phone,
            role="client",
        )
        session.add(user)
        await session.flush()

    total = 0
    order_items_data = []
    for item in payload.items:
        product_result = await session.execute(select(Product).where(Product.id == item.product_id))
        product = product_result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=400, detail=f"Product {item.product_id} not found")
        item_total = product.price * item.quantity
        total += item_total
        order_items_data.append({
            "product": product,
            "quantity": item.quantity,
            "price": product.price,
            "total": item_total,
        })

    order = Order(
        order_number=f"KS-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        user_id=user.id,
        shop_id=payload.shop_id,
        status=OrderStatus.NEW,
        total_amount=total,
        delivery_type=payload.delivery,
        customer_name=payload.name,
        customer_phone=payload.phone,
        customer_city=payload.city,
        comment=payload.comment or "",
    )
    session.add(order)
    await session.flush()

    for item_data in order_items_data:
        product = item_data["product"]
        session.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            quantity=item_data["quantity"],
            price=item_data["price"],
            total=item_data["total"],
        ))

    await session.commit()

    # Reload order with relationships for LiveSklad sync
    result = await session.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.shop),
            selectinload(Order.user),
        )
    )
    order = result.scalar_one()

    try:
        livesklad_id = await create_livesklad_order(order)
        order.livesklad_order_id = livesklad_id
        order.sync_status = SyncStatus.SUCCESS
    except Exception as e:
        order.status = OrderStatus.PENDING_SYNC
        order.sync_status = SyncStatus.ERROR
        order.sync_message = str(e)[:500]

    await session.commit()

    bot = await _get_bot()
    if bot:
        try:
            await notify_admins_new_order(bot, order)
            await notify_user_order_status(bot, payload.telegram_id, order)
        except Exception:
            logging.exception("Failed to notify about order %s", order.id)

    return {
        "id": order.id,
        "number": order.order_number,
        "total": float(order.total_amount),
        "status": order.status.value,
        "sync_status": order.sync_status.value if hasattr(order.sync_status, "value") else order.sync_status,
    }


@router.get("/orders")
async def list_orders(
    telegram_id: int = Depends(verify_telegram_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Order)
        .join(User)
        .where(User.telegram_id == telegram_id)
        .order_by(desc(Order.created_at))
    )
    result = await session.execute(stmt.limit(100).options(
        selectinload(Order.items),
        selectinload(Order.shop),
    ))
    orders = result.scalars().all()
    return [
        {
            "id": o.id,
            "number": o.order_number,
            "status": o.status.value,
            "total": float(o.total_amount),
            "customer": o.customer_name,
            "phone": o.customer_phone,
            "sync_status": o.sync_status.value,
            "created_at": o.created_at.isoformat(),
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "quantity": i.quantity,
                    "price": float(i.price) if i.price else None,
                }
                for i in o.items
            ],
            "shop": o.shop.name if o.shop else None,
        }
        for o in orders
    ]


class ProfilePhoneUpdate(BaseModel):
    phone: str = Field(..., min_length=5, max_length=30)


@router.post("/profile/phone")
async def update_profile_phone(
    payload: ProfilePhoneUpdate,
    telegram_id: int = Depends(verify_telegram_user),
    session: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_user(session, telegram_id)
    user.phone = payload.phone.strip()
    await session.commit()
    return {"ok": True}


LEAD_SUBJECTS = {
    "best_price": "Узнать лучшую цену",
    "contact_manager": "Вопрос менеджеру",
    "gift": "Подобрать подарок к 8 марта",
    "price_today": "Узнать лучшую цену сегодня",
    "installment": "Рассрочка 0%: узнать условия",
}


class LeadCreate(BaseModel):
    source: Literal["product", "best_price", "contact_manager", "gift", "price_today", "installment"]
    product_id: int | None = Field(None, ge=1)
    message: str | None = Field(None, max_length=1000)


@router.post("/leads")
async def create_lead(
    payload: LeadCreate,
    telegram_id: int = Depends(verify_telegram_user),
    session: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_user(session, telegram_id)
    if not user.phone:
        raise HTTPException(status_code=409, detail="phone_required")

    product = None
    if payload.product_id:
        product_result = await session.execute(select(Product).where(Product.id == payload.product_id))
        product = product_result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=400, detail="Product not found")

    if payload.source == "product":
        subject = product.name if product else "Заявка на товар"
    else:
        subject = LEAD_SUBJECTS[payload.source]

    order = Order(
        order_number=f"KS-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        user_id=user.id,
        status=OrderStatus.NEW,
        total_amount=product.price if product else 0,
        delivery_type=subject,
        customer_name=user.name or "Клиент",
        customer_phone=user.phone,
        comment=payload.message or subject,
        sync_status=SyncStatus.PENDING,
    )
    session.add(order)
    await session.flush()

    if product:
        session.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            quantity=1,
            price=product.price,
            total=product.price,
        ))

    await session.commit()

    result = await session.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.user),
            selectinload(Order.shop),
        )
    )
    order = result.scalar_one()

    if product:
        try:
            livesklad_id = await create_livesklad_order(order)
            order.livesklad_order_id = livesklad_id
            order.sync_status = SyncStatus.SUCCESS
        except Exception as e:
            order.status = OrderStatus.PENDING_SYNC
            order.sync_status = SyncStatus.ERROR
            order.sync_message = str(e)[:500]
        await session.commit()

    bot = await _get_bot()
    if bot:
        try:
            await notify_admins_new_order(bot, order)
            await notify_user_order_status(bot, telegram_id, order)
        except Exception:
            logging.exception("Failed to notify about lead %s", order.id)

    return {"id": order.id, "number": order.order_number, "subject": subject}


class TradeInCreate(BaseModel):
    device_type: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=200)
    memory: str | None = Field(None, max_length=50)
    battery: str = Field(..., min_length=1, max_length=100)
    condition: str = Field(..., min_length=1, max_length=100)


@router.post("/tradeins")
async def create_tradein(
    payload: TradeInCreate,
    telegram_id: int = Depends(verify_telegram_user),
    session: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_user(session, telegram_id)

    model_text = f"{payload.model} {payload.memory}".strip() if payload.memory else payload.model
    tradein = TradeIn(
        user_id=user.id,
        device_type=payload.device_type,
        model=model_text,
        battery_condition=payload.battery,
        device_condition=payload.condition,
        status=TradeInStatus.NEW,
    )
    session.add(tradein)
    await session.commit()

    result = await session.execute(
        select(TradeIn).where(TradeIn.id == tradein.id).options(selectinload(TradeIn.user))
    )
    tradein = result.scalar_one()

    try:
        livesklad_id = await create_livesklad_tradein(tradein)
        tradein.livesklad_id = livesklad_id
        await session.commit()
    except Exception:
        logging.exception("Failed to sync trade-in %s to LiveSklad", tradein.id)

    bot = await _get_bot()
    if bot:
        try:
            await notify_admins_tradein(bot, tradein)
        except Exception:
            logging.exception("Failed to notify admins about trade-in %s", tradein.id)

    return {"id": tradein.id}


@router.get("/tradeins")
async def list_tradeins(session: AsyncSession = Depends(get_db), _=Depends(_check_admin)):
    from sqlalchemy import desc
    result = await session.execute(select(TradeIn).order_by(desc(TradeIn.created_at)).limit(100))
    tradeins = result.scalars().all()
    return [
        {
            "id": t.id,
            "device_type": t.device_type,
            "model": t.model,
            "battery": t.battery_condition,
            "condition": t.device_condition,
            "status": t.status.value,
            "created_at": t.created_at.isoformat(),
        }
        for t in tradeins
    ]


@router.get("/giveaways")
async def list_giveaways(session: AsyncSession = Depends(get_db)):
    from sqlalchemy import desc
    result = await session.execute(select(Giveaway).order_by(desc(Giveaway.created_at)).limit(100))
    giveaways = result.scalars().all()
    return [
        {
            "id": g.id,
            "title": g.title,
            "prize": g.prize,
            "status": g.status.value,
            "created_at": g.created_at.isoformat(),
        }
        for g in giveaways
    ]


async def _optional_telegram_user(x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data")) -> int | None:
    if not x_telegram_init_data:
        return None
    return get_validated_user_id(x_telegram_init_data)


@router.get("/giveaways/{giveaway_id}")
async def get_giveaway(
    giveaway_id: int,
    telegram_id: int | None = Depends(_optional_telegram_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Giveaway).where(Giveaway.id == giveaway_id))
    giveaway = result.scalar_one_or_none()
    if not giveaway:
        raise HTTPException(status_code=404, detail="Giveaway not found")

    my_tickets = 0
    invited_count = 0
    joined = False
    if telegram_id is not None:
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if user:
            p_result = await session.execute(
                select(GiveawayParticipant).where(
                    GiveawayParticipant.giveaway_id == giveaway_id,
                    GiveawayParticipant.user_id == user.id,
                )
            )
            participant = p_result.scalar_one_or_none()
            if participant:
                joined = True
                my_tickets = participant.tickets
                invited_count = participant.invited_count

    return {
        "id": giveaway.id,
        "title": giveaway.title,
        "description": giveaway.description,
        "prize": giveaway.prize,
        "status": giveaway.status.value,
        "channel_url": giveaway.channel_url,
        "joined": joined,
        "my_tickets": my_tickets,
        "invited_count": invited_count,
    }


@router.post("/giveaways/{giveaway_id}/join")
async def join_giveaway(
    giveaway_id: int,
    telegram_id: int = Depends(verify_telegram_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(Giveaway).where(Giveaway.id == giveaway_id))
    giveaway = result.scalar_one_or_none()
    if not giveaway:
        raise HTTPException(status_code=404, detail="Giveaway not found")

    user = await _get_or_create_user(session, telegram_id)

    p_result = await session.execute(
        select(GiveawayParticipant).where(
            GiveawayParticipant.giveaway_id == giveaway_id,
            GiveawayParticipant.user_id == user.id,
        )
    )
    participant = p_result.scalar_one_or_none()
    if not participant:
        participant = GiveawayParticipant(giveaway_id=giveaway_id, user_id=user.id)
        session.add(participant)
        await session.commit()

    return {"joined": True, "my_tickets": participant.tickets, "invited_count": participant.invited_count}


@router.post("/giveaways/{giveaway_id}/invite")
async def invite_to_giveaway(
    giveaway_id: int,
    telegram_id: int = Depends(verify_telegram_user),
    session: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_user(session, telegram_id)

    p_result = await session.execute(
        select(GiveawayParticipant).where(
            GiveawayParticipant.giveaway_id == giveaway_id,
            GiveawayParticipant.user_id == user.id,
        )
    )
    participant = p_result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=400, detail="Join the giveaway first")

    participant.invited_count += 1
    participant.tickets += 1
    await session.commit()

    return {"my_tickets": participant.tickets, "invited_count": participant.invited_count}


@router.post("/sync")
async def trigger_sync(session: AsyncSession = Depends(get_db), _=Depends(_check_admin)):
    # На хостингах без отдельного Celery-воркера (например, Bothost) задача,
    # поставленная через .delay(), никогда не будет выполнена — некому её
    # забрать из очереди. Поэтому синхронизацию запускаем прямо здесь и ждём
    # результат, а не полагаемся на брокер.
    try:
        stats = await sync_products(session)
        return {"status": "ok", **stats}
    except Exception as e:
        logging.exception("Manual Google Sheets sync failed")
        raise HTTPException(status_code=502, detail=f"Синхронизация не удалась: {e}")


@router.post("/sync/webhook")
async def sync_webhook(token: str | None = None, session: AsyncSession = Depends(get_db)):
    # Отдельный эндпоинт без cookie-авторизации админки — предназначен для
    # вызова из Google Apps Script (триггер onEdit на самой таблице), чтобы
    # изменения в таблице подтягивались за секунды, а не ждали периодический
    # опрос по таймеру. Работает только если задан GOOGLE_SHEETS_SYNC_TOKEN,
    # иначе эндпоинт полностью отключён (иначе кто угодно мог бы дёргать синк).
    if not settings.GOOGLE_SHEETS_SYNC_TOKEN:
        raise HTTPException(status_code=404, detail="Sync webhook is not configured")
    if token != settings.GOOGLE_SHEETS_SYNC_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    try:
        stats = await sync_products(session)
        return {"status": "ok", **stats}
    except Exception as e:
        logging.exception("Webhook Google Sheets sync failed")
        raise HTTPException(status_code=502, detail=f"Синхронизация не удалась: {e}")


@router.get("/logs")
async def list_logs(limit: int = 20, session: AsyncSession = Depends(get_db), _=Depends(_check_admin)):
    from sqlalchemy import desc
    result = await session.execute(select(SyncLog).order_by(desc(SyncLog.created_at)).limit(limit))
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "source": l.source,
            "status": l.status.value,
            "message": l.message,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
