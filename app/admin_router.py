import hmac
import hashlib
import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

import filetype
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import settings
from app.models import Category, Product


def _admin_secret() -> bytes:
    key = settings.WEBHOOK_SECRET or settings.BOT_TOKEN or settings.ADMIN_PASSWORD
    return hashlib.sha256(key.encode()).digest()


def _create_admin_token() -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    payload = f"admin|{int(expires.timestamp())}"
    sig = hmac.new(_admin_secret(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}|{sig}"


def _verify_admin_token(token: str) -> bool:
    if not token or "|" not in token:
        return False
    try:
        payload, sig = token.rsplit("|", 1)
        _, exp_ts = payload.split("|", 1)
        if int(exp_ts) < datetime.now(timezone.utc).timestamp():
            return False
        expected = hmac.new(_admin_secret(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    image_url: str | None = Field(None, max_length=1000)
    icon_emoji: str | None = Field(None, max_length=50)
    tile_size: str = Field("medium")
    sort_order: int = Field(0, ge=0)
    is_active: bool = True

    @validator("tile_size")
    def validate_tile_size(cls, v):
        allowed = {"small", "medium", "large", "wide"}
        if v not in allowed:
            raise ValueError(f"tile_size must be one of {allowed}")
        return v


class CategoryUpdate(CategoryCreate):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    category: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, max_length=100)
    memory: str | None = Field(None, max_length=50)
    photo_url: str | None = Field(None, max_length=1000)
    price: float | None = Field(None, ge=0)
    stock: int | None = Field(None, ge=0)
    status: str | None = Field(None, max_length=20)


router = APIRouter(prefix="/admin", tags=["admin"])

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"
ADMIN_HTML = WEBAPP_DIR / "admin.html"
UPLOADS_DIR = WEBAPP_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


def _check_admin(request: Request):
    token = request.cookies.get("admin_token") or ""
    if not _verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("", response_class=FileResponse)
async def admin_page():
    return FileResponse(str(ADMIN_HTML))


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie("admin_token")
    return {"ok": True}


@router.post("/login")
async def admin_login(request: Request, response: Response, password: str = Form(...)):
    if not hmac.compare_digest(
        settings.ADMIN_PASSWORD.encode(),
        password.encode(),
    ):
        raise HTTPException(status_code=401, detail="Invalid password")
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    token = _create_admin_token()
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        expires=expire,
    )
    return {"ok": True}


@router.get("/api/categories")
async def list_categories(session: AsyncSession = Depends(get_db), _=Depends(_check_admin)):
    result = await session.execute(select(Category).order_by(Category.sort_order, Category.name))
    rows = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "image_url": c.image_url,
            "icon_emoji": c.icon_emoji,
            "tile_size": c.tile_size,
            "sort_order": c.sort_order,
            "is_active": c.is_active,
        }
        for c in rows
    ]


@router.post("/api/categories")
async def create_category(
    data: CategoryCreate,
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
):
    cat = Category(
        name=data.name.strip(),
        description=data.description,
        image_url=data.image_url,
        icon_emoji=data.icon_emoji,
        tile_size=data.tile_size,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    session.add(cat)
    await session.commit()
    return {"id": cat.id}


@router.put("/api/categories/{category_id}")
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
):
    result = await session.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.name = data.name.strip()
    cat.description = data.description
    cat.image_url = data.image_url
    cat.icon_emoji = data.icon_emoji
    cat.tile_size = data.tile_size
    cat.sort_order = data.sort_order
    cat.is_active = data.is_active
    await session.commit()
    return {"ok": True}


@router.delete("/api/categories/{category_id}")
async def delete_category(
    category_id: int,
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
):
    result = await session.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await session.delete(cat)
    await session.commit()
    return {"ok": True}


@router.get("/api/products")
async def list_products(
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
    q: str = "",
):
    stmt = select(Product).order_by(Product.name)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    result = await session.execute(stmt.limit(200))
    rows = result.scalars().all()
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "color": p.color,
            "memory": p.memory,
            "photo_url": p.photo_url,
            "price": float(p.price) if p.price else None,
            "stock": p.stock,
            "status": p.status.value,
        }
        for p in rows
    ]


@router.put("/api/products/{product_id}")
async def update_product(
    product_id: int,
    data: ProductUpdate,
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
):
    result = await session.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    if data.name is not None:
        p.name = data.name.strip()
    if data.category is not None:
        p.category = data.category.strip()
    if data.color is not None:
        p.color = data.color
    if data.memory is not None:
        p.memory = data.memory
    if data.photo_url is not None:
        p.photo_url = data.photo_url
    if data.price is not None:
        p.price = data.price
    if data.stock is not None:
        p.stock = data.stock
    if data.status is not None:
        p.status = data.status
    await session.commit()
    return {"ok": True}


@router.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    _=Depends(_check_admin),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files allowed")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    kind = filetype.guess(content)
    if not kind or not kind.mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file")

    ext = Path(file.filename or "").suffix.lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if ext not in allowed_exts:
        ext = f".{kind.extension}"
    if ext not in allowed_exts:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOADS_DIR / filename
    with open(dest, "wb") as f:
        f.write(content)
    url = f"/webapp/uploads/{filename}"
    return {"url": url}
