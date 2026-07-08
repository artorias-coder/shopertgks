from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.config import settings

engine_kwargs = {"echo": False}
if settings.is_sqlite:
    # SQLite async требует специальных параметров
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL: устойчивые настройки пула для PaaS
    if settings.REDIS_URL:
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = 300
    else:
        # Без Redis/серверless окружение: NullPool избегает зависших соединений
        engine_kwargs["poolclass"] = NullPool

if settings.is_sqlite:
    engine_kwargs.setdefault("connect_args", {})["check_same_thread"] = False
else:
    engine_kwargs.setdefault("connect_args", {})["timeout"] = 10

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
