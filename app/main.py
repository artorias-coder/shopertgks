from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, engine
from app.models import Base
from app.api.routers import router as api_router
from app.config import settings

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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/orders")
async def list_orders(session: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models import Order
    result = await session.execute(select(Order))
    orders = result.scalars().all()
    return [{"id": o.id, "number": o.order_number, "status": o.status.value} for o in orders]
