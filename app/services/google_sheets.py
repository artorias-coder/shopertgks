import csv
import io
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models import Product, ProductStatus, Shop, ProductStock, SyncLog, SyncStatus
from app.config import settings
from app.services.livesklad import fetch_shops
from app.services.product_specs import extract_color, extract_memory, get_specs


def _upsert_stmt(table):
    """Pick the right dialect-specific upsert builder (Bothost free plan may run on SQLite)."""
    return sqlite_insert(table) if settings.is_sqlite else pg_insert(table)


SHEET_EXPORT_URL = "https://docs.google.com/spreadsheets/d/{id}/export?format=csv"


def _clean_str(value):
    """str(None) == 'None' — обычный str(x) or None превращает отсутствующее
    значение в буквальную строку 'None', которая потом всплывает в интерфейсе
    ("AirPods 3 Original None None"). None должен оставаться None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_price(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    # Remove ₽, spaces, non-breaking spaces, replace comma decimal
    cleaned = str(value).replace("₽", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


CATEGORY_ALIASES = {
    "2": "iPhone",
    "iphone": "iPhone",
    "ipad": "iPad",
    "mac": "Mac",
    "watch": "Apple Watch",
    "airpods": "AirPods",
    "vision": "Vision",
}


def _normalize_category(name: str) -> str:
    key = name.strip().lower()
    return CATEGORY_ALIASES.get(key, name.strip())


def _build_sku(row: dict) -> str:
    parts = [row.get("name", ""), row.get("storage", ""), row.get("color", ""), row.get("sim", "")]
    clean = "_".join(p.strip().replace(" ", "_").replace("\xa0", "_") for p in parts if p.strip())
    return clean.lower()[:100]


def _parse_sheet_csv(content: str):
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return []

    header = [h.strip().lower() for h in rows[0]]
    data_rows = rows[1:]
    products = []

    for row in data_rows:
        if not row:
            continue

        # Build a dict from header columns
        data = {}
        for i, key in enumerate(header):
            data[key] = row[i].strip() if i < len(row) else ""

        name = data.get("name", "")
        if not name:
            continue

        # Реальная структура таблицы (проверено на актуальной выгрузке):
        # ID, Category, Name, Полная группа, price, price_sale, photo_url, description
        # "price" — обычная/старая цена, "price_sale" — цена продажи (со скидкой).
        # Старые форматы с "price_card"/числовыми колонками "1"/"2" поддержаны как fallback.
        if "price" in data or "price_sale" in data:
            base_price = _parse_price(data.get("price", ""))
            sale_price = _parse_price(data.get("price_sale", ""))
            if sale_price is not None:
                cash_price = sale_price
                card_price = base_price if base_price is not None and base_price > sale_price else None
            else:
                cash_price = base_price
                card_price = None
        elif "price_card" in data:
            cash_price = _parse_price(data.get("price_sale", ""))
            card_price = _parse_price(data.get("price_card", ""))
        else:
            cash_price = _parse_price(data.get("2", ""))
            card_price = _parse_price(data.get("1", ""))

        if cash_price is None:
            continue

        # Спецкоды вместо цены: 1 = товара нет в наличии, 2 = продаётся только
        # под заказ. Это не реальная цена, поэтому обнуляем её и цену "было",
        # а карточка товара на фронте показывает статус вместо суммы.
        status_override = None
        if cash_price == 1:
            status_override = "out_of_stock"
            cash_price = 0
            card_price = None
        elif cash_price == 2:
            status_override = "on_request"
            cash_price = 0
            card_price = None

        category = _normalize_category(data.get("category", "iPhone"))
        color = extract_color(data.get("color", "")) or extract_color(name)
        memory = data.get("storage", "") or extract_memory(name)
        specs = get_specs(name)
        sim = data.get("sim", "")
        # f"{name} {memory} {color}" вставляет буквальный текст "None", если
        # memory/color не определены (обычное дело — в таблице этих колонок
        # нет вовсе) — отсюда "AirPods 3 Original None None" в заголовке.
        display_name = " ".join(part for part in (name, memory, color) if part).strip()
        if sim:
            display_name += f" ({sim})"

        sheet_id = data.get("id", "").strip()
        if sheet_id:
            # Уникальный ID из таблицы даёт стабильный и коллизионно-безопасный SKU
            # (в отличие от построения из текста имени, которое может совпасть
            # у разных товаров, например одинаковые модели без цвета/памяти).
            sku = f"gs{sheet_id}"
        else:
            sku = _build_sku({"name": name, "storage": memory, "color": color or "", "sim": sim})

        # photo_url раньше вообще не читался из таблицы — все товары уходили без фото.
        photo_url = data.get("photo_url", "").strip()
        if photo_url and not photo_url.lower().startswith(("http://", "https://")):
            # В таблице встречаются некорректные значения вида
            # "airpods-1.png (2400×2400)" — это не ссылка, а имя файла с размером.
            photo_url = ""

        # description раньше всегда затирался общей заглушкой "Категория: X",
        # даже если в таблице было реальное описание.
        sheet_description = data.get("description", "").strip()
        description = sheet_description or f"Категория: {category}"

        products.append({
            "sku": sku,
            "name": display_name,
            "category": category,
            "price": cash_price,
            "old_price": card_price,
            "discount": card_price - cash_price if card_price and cash_price else None,
            "description": description,
            "color": color,
            "memory": memory,
            "specs": specs,
            "stock": 0 if status_override else 1,
            "photo_url": photo_url or None,
            "status": status_override or "active",
        })

    return products


async def _fetch_csv() -> str:
    if not settings.GOOGLE_SHEETS_ID:
        raise RuntimeError("GOOGLE_SHEETS_ID not configured")
    url = SHEET_EXPORT_URL.format(id=settings.GOOGLE_SHEETS_ID)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        return response.text


async def sync_products(session: AsyncSession) -> dict:
    content = await _fetch_csv()
    rows = _parse_sheet_csv(content)
    stats = {"created": 0, "updated": 0, "hidden": 0, "errors": 0}

    existing_stmt = select(Product.sku)
    existing_result = await session.execute(existing_stmt)
    existing_skus = {r for r in existing_result.scalars().all()}
    seen_skus = set()

    for row in rows:
        try:
            sku = str(row.get("sku", "")).strip()
            if not sku:
                continue
            seen_skus.add(sku)

            status = str(row.get("status", "active")).strip().lower()
            try:
                # ВАЖНО: ProductStatus.__members__ хранит ключи по ИМЕНИ ("ACTIVE"),
                # а не по значению ("active") — старая проверка "status in __members__"
                # никогда не срабатывала для строчных значений, поэтому статус из
                # таблицы (out_of_stock/on_request/hidden) тут просто игнорировался.
                product_status = ProductStatus(status)
            except ValueError:
                product_status = ProductStatus.ACTIVE

            values = {
                "livesklad_id": _clean_str(row.get("livesklad_id")),
                "name": str(row.get("name", "")),
                "category": str(row.get("category", "")),
                "subcategory": _clean_str(row.get("subcategory")),
                "description": _clean_str(row.get("description")),
                "color": _clean_str(row.get("color")),
                "memory": _clean_str(row.get("memory")),
                "specs": row.get("specs") if isinstance(row.get("specs"), dict) else None,
                "price": parse_price(row.get("price", 0)),
                "old_price": parse_price(row.get("old_price")) if row.get("old_price") else None,
                "discount": parse_price(row.get("discount")) if row.get("discount") else None,
                "stock": int(row.get("stock", 0) or 0),
                "photo_url": _clean_str(row.get("photo_url")),
                "status": product_status,
            }

            stmt = _upsert_stmt(Product).values(sku=sku, **values).on_conflict_do_update(
                index_elements=["sku"],
                set_=values,
            )
            await session.execute(stmt)
            if sku not in existing_skus:
                stats["created"] += 1
            else:
                stats["updated"] += 1

            if product_status in (ProductStatus.HIDDEN, ProductStatus.OUT_OF_STOCK):
                stats["hidden"] += 1
        except Exception as e:
            stats["errors"] += 1
            log = SyncLog(
                source="google_sheets",
                entity_type="product",
                entity_id=str(row.get("sku", "")),
                status=SyncStatus.ERROR,
                message=str(e),
            )
            session.add(log)

    # Archive products not in sheet anymore
    missing_stmt = select(Product).where(Product.sku.notin_(seen_skus), Product.status != ProductStatus.ARCHIVED)
    missing_result = await session.execute(missing_stmt)
    for product in missing_result.scalars().all():
        product.status = ProductStatus.ARCHIVED

    await _sync_shops(session)
    await _ensure_default_stock(session, seen_skus)

    success_log = SyncLog(
        source="google_sheets",
        entity_type="products",
        status=SyncStatus.SUCCESS,
        message=f"Created: {stats['created']}, Updated: {stats['updated']}, Hidden: {stats['hidden']}, Errors: {stats['errors']}",
    )
    session.add(success_log)
    await session.commit()
    return stats


async def _sync_shops(session: AsyncSession) -> None:
    try:
        shops = await fetch_shops()
    except Exception as e:
        session.add(SyncLog(
            source="livesklad_shops",
            entity_type="shops",
            status=SyncStatus.ERROR,
            message=str(e),
        ))
        return

    for shop in shops:
        shop_id = shop.get("id")
        if not shop_id:
            continue
        stmt = _upsert_stmt(Shop).values(
            livesklad_id=shop_id,
            name=shop.get("name", ""),
            address=shop.get("address", ""),
            color=shop.get("color", ""),
            is_active=True,
        ).on_conflict_do_update(
            index_elements=["livesklad_id"],
            set_={
                "name": shop.get("name", ""),
                "address": shop.get("address", ""),
                "color": shop.get("color", ""),
            },
        )
        await session.execute(stmt)


async def _ensure_default_stock(session: AsyncSession, skus: set[str]) -> None:
    if not skus:
        return

    shop_stmt = select(Shop).where(Shop.is_active == True)
    shop_result = await session.execute(shop_stmt)
    shops = shop_result.scalars().all()
    if not shops:
        return

    product_stmt = select(Product).where(Product.sku.in_(skus))
    product_result = await session.execute(product_stmt)
    products = product_result.scalars().all()

    for product in products:
        total = 0
        for shop in shops:
            stock_stmt = select(ProductStock).where(
                ProductStock.product_id == product.id,
                ProductStock.shop_id == shop.id,
            )
            stock_result = await session.execute(stock_stmt)
            stock = stock_result.scalar_one_or_none()
            if stock is None:
                stock = ProductStock(product_id=product.id, shop_id=shop.id, quantity=1)
                session.add(stock)
                total += 1
            else:
                total += stock.quantity
        product.stock = total

    await session.commit()


def parse_price(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", ".").replace(" ", ""))
