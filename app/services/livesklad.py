import time
import httpx
from app.config import settings
from app.models import Order, TradeIn, SyncLog, SyncStatus


_token_cache = {"token": None, "expires_at": 0}


async def _get_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    if not settings.LIVESKLAD_API_LOGIN or not settings.LIVESKLAD_API_PASSWORD:
        raise RuntimeError("LIVESKLAD_API_LOGIN и LIVESKLAD_API_PASSWORD не настроены")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.LIVESKLAD_BASE_URL}/auth",
            data={"login": settings.LIVESKLAD_API_LOGIN, "password": settings.LIVESKLAD_API_PASSWORD},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("data", {}).get("token", data.get("token"))
        ttl = data.get("data", {}).get("ttl", data.get("ttl", 900))
        if not token:
            raise RuntimeError("LiveSklad не вернул токен")

    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + ttl - 60
    return token


async def _api_request(method: str, path: str, **kwargs):
    token = await _get_token()
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{settings.LIVESKLAD_BASE_URL}{path}",
            headers={"Authorization": token},
            timeout=30.0,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()


async def fetch_shops() -> list[dict]:
    data = await _api_request("GET", "/shops")
    return data.get("data", [])


async def _get_type_order_id(kind: str = "default") -> str:
    if kind == "tradein" and settings.LIVESKLAD_TRADEIN_TYPE_ORDER_ID:
        return settings.LIVESKLAD_TRADEIN_TYPE_ORDER_ID
    if settings.LIVESKLAD_TYPE_ORDER_ID:
        return settings.LIVESKLAD_TYPE_ORDER_ID

    data = await _api_request("GET", "/type-orders")
    types = data.get("data", [])
    if not types:
        raise RuntimeError("Не найдено ни одного типа заказа в LiveSklad")
    return types[0]["id"]


async def create_livesklad_order(order: Order, kind: str = "default") -> str:
    shop_id = order.shop.livesklad_id if (order.shop and order.shop.livesklad_id) else settings.LIVESKLAD_SHOP_ID
    if not shop_id:
        raise RuntimeError("LIVESKLAD_SHOP_ID не настроен")

    type_order_id = await _get_type_order_id(kind)

    items_text = "\n".join(
        f"{item.name} — {item.quantity} шт. × {item.price} ₽"
        for item in order.items
    )
    order_note = (
        f"{order.comment}\n\n"
        f"Товары:\n{items_text}\n\n"
        f"Итого: {order.total_amount} ₽"
    )

    payload = {
        "typeOrderId": type_order_id,
        "name": order.customer_name or "Клиент",
        "phones": [order.customer_phone] if order.customer_phone else [],
        "isBuyer": True,
        "orderNode": order_note,
    }

    data = await _api_request(
        "POST",
        f"/shops/{shop_id}/orders",
        json=payload,
    )
    return str(data.get("data", {}).get("id", ""))


async def create_livesklad_tradein(tradein: TradeIn) -> str:
    if not settings.LIVESKLAD_SHOP_ID:
        raise RuntimeError("LIVESKLAD_SHOP_ID не настроен")

    type_order_id = await _get_type_order_id("tradein")
    order_note = (
        f"Заявка Trade-in из Telegram-бота\n\n"
        f"Тип устройства: {tradein.device_type}\n"
        f"Модель: {tradein.model}\n"
        f"Состояние батареи: {tradein.battery_condition}\n"
        f"Состояние устройства: {tradein.device_condition}\n"
        f"Оценочная цена: {tradein.estimated_price or 'не указана'}"
    )

    user = tradein.user
    payload = {
        "typeOrderId": type_order_id,
        "name": user.name or "Клиент",
        "phones": [user.phone] if user.phone else [],
        "isBuyer": True,
        "orderNode": order_note,
        "typeDevice": tradein.device_type,
        "brand": tradein.device_type,
        "model": tradein.model,
    }

    data = await _api_request(
        "POST",
        f"/shops/{settings.LIVESKLAD_SHOP_ID}/orders",
        json=payload,
    )
    return str(data.get("data", {}).get("id", ""))
