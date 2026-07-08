import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import settings
from app.models import Category, Product


router = APIRouter(prefix="/admin", tags=["admin"])

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"
ADMIN_HTML = WEBAPP_DIR / "admin.html"
UPLOADS_DIR = WEBAPP_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


def _check_admin(request: Request):
    token = request.cookies.get("admin_token") or ""
    expected = f"{settings.ADMIN_PASSWORD}:valid"
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("", response_class=FileResponse)
async def admin_page():
    return FileResponse(str(ADMIN_HTML))


@router.post("/logout")
async def admin_logout(response: Response):
    response.delete_cookie("admin_token")
    return {"ok": True}


@router.post("/login")
async def admin_login(response: Response, password: str = Form(...)):
    if password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    response.set_cookie(
        key="admin_token",
        value=f"{settings.ADMIN_PASSWORD}:valid",
        httponly=True,
        secure=False,
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
    request: Request,
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
):
    data = await request.json()
    cat = Category(
        name=data.get("name", "").strip(),
        description=data.get("description"),
        image_url=data.get("image_url"),
        icon_emoji=data.get("icon_emoji"),
        tile_size=data.get("tile_size", "medium"),
        sort_order=int(data.get("sort_order", 0) or 0),
        is_active=bool(data.get("is_active", True)),
    )
    session.add(cat)
    await session.commit()
    return {"id": cat.id}


@router.put("/api/categories/{category_id}")
async def update_category(
    category_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
):
    data = await request.json()
    result = await session.execute(select(Category).where(Category.id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.name = data.get("name", cat.name).strip()
    cat.description = data.get("description", cat.description)
    cat.image_url = data.get("image_url", cat.image_url)
    cat.icon_emoji = data.get("icon_emoji", cat.icon_emoji)
    cat.tile_size = data.get("tile_size", cat.tile_size)
    cat.sort_order = int(data.get("sort_order", cat.sort_order) or 0)
    cat.is_active = bool(data.get("is_active", cat.is_active))
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
    request: Request,
    session: AsyncSession = Depends(get_db),
    _=Depends(_check_admin),
):
    data = await request.json()
    result = await session.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    p.name = data.get("name", p.name).strip()
    p.category = data.get("category", p.category)
    p.color = data.get("color", p.color)
    p.memory = data.get("memory", p.memory)
    p.photo_url = data.get("photo_url", p.photo_url)
    p.stock = int(data.get("stock", p.stock) or 0)
    if "price" in data and data["price"] is not None:
        p.price = float(data["price"])
    await session.commit()
    return {"ok": True}


@router.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    _=Depends(_check_admin),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files allowed")
    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOADS_DIR / filename
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    with open(dest, "wb") as f:
        f.write(content)
    url = f"/webapp/uploads/{filename}"
    return {"url": url}
