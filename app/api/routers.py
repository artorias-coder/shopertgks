import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field, validator

from app.database import get_db
from app.models import Product, Order, OrderItem, OrderStatus, ProductStatus, Shop, ProductStock, SyncLog, SyncStatus, TradeIn, Giveaway, User
from app.services.google_sheets import sync_products
from app.services.livesklad import create_livesklad_order
from app.services.telegram_webapp import validate_init_data
from app.tasks import sync_google_sheets


def verify_telegram_init_data(x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data")):
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram init data")
    if not validate_init_data(x_telegram_init_data):
        raise HTTPException(status_code=403, detail="Invalid Telegram init data")

router = APIRouter()


@router.get("/products")
async def list_products(category: str | None = None, session: AsyncSession = Depends(get_db)):
    stmt = select(Product).where(Product.status == ProductStatus.ACTIVE)
    if category:
        stmt = stmt.where(Product.category == category)
    result = await session.execute(stmt.order_by(Product.name))
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
    result = await session.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
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

    return {
        "id": order.id,
        "number": order.order_number,
        "total": float(order.total_amount),
        "status": order.status.value,
        "sync_status": order.sync_status.value if hasattr(order.sync_status, "value") else order.sync_status,
    }


@router.get("/orders")
async def list_orders(telegram_id: int | None = None, session: AsyncSession = Depends(get_db)):
    stmt = select(Order).order_by(desc(Order.created_at))
    if telegram_id:
        stmt = stmt.join(User).where(User.telegram_id == telegram_id)
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


@router.get("/tradeins")
async def list_tradeins(session: AsyncSession = Depends(get_db)):
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


@router.post("/sync")
async def trigger_sync():
    sync_google_sheets.delay()
    return {"status": "queued"}


@router.get("/logs")
async def list_logs(limit: int = 20, session: AsyncSession = Depends(get_db)):
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
