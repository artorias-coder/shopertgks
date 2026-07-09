import sys
import uvicorn
import logging
from pathlib import Path

# Добавляем корень проекта в путь, чтобы импортировать app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("bothost")

print("BOTHOST_STARTUP: entering bothost.py", flush=True)

try:
    from app.config import settings
except Exception as e:
    logger.exception("Failed to load settings")
    print(f"BOTHOST_FATAL: {e}", file=sys.stderr, flush=True)
    print("BOTHOST_HINT: set BOT_TOKEN and DATABASE_URL env vars", file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == "__main__":
    host = settings.APP_HOST
    port = settings.app_port
    logger.info(f"Starting KingStore API on {host}:{port}")
    logger.info(f"DATABASE_URL present: {bool(settings.DATABASE_URL)}")
    logger.info(f"DATABASE_URL scheme: {settings.DATABASE_URL.split('://')[0] if settings.DATABASE_URL else 'none'}")
    logger.info(f"BOT_TOKEN present: {bool(settings.BOT_TOKEN)}")
    logger.info(f"WEBHOOK_URL: {settings.WEBHOOK_URL}")
    logger.info(f"WEBAPP_URL: {settings.WEBAPP_URL}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
