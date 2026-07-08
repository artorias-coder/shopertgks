import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import startup
from app.database import engine


async def main():
    async with engine.begin() as conn:
        from app.models import Base
        await conn.run_sync(Base.metadata.create_all)
    print("Таблицы созданы")


if __name__ == "__main__":
    asyncio.run(main())
