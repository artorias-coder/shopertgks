import os
import sys
import uvicorn
from pathlib import Path

# Добавляем корень проекта в путь, чтобы импортировать app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings


if __name__ == "__main__":
    host = settings.APP_HOST
    port = settings.app_port
    print(f"Starting KingStore API on {host}:{port}", flush=True)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=settings.LOG_LEVEL.lower(),
    )
