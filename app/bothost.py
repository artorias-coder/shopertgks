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


VALID_LOG_LEVELS = {"critical", "error", "warning", "info", "debug", "trace"}


if __name__ == "__main__":
    host = settings.APP_HOST
    port = settings.app_port
    logger.info(f"Starting KingStore API on {host}:{port}")
    logger.info(f"DATABASE_URL present: {bool(settings.DATABASE_URL)}")
    logger.info(f"DATABASE_URL scheme: {settings.DATABASE_URL.split('://')[0] if settings.DATABASE_URL else 'none'}")
    logger.info(f"BOT_TOKEN present: {bool(settings.BOT_TOKEN)}")
    logger.info(f"WEBHOOK_URL: {settings.WEBHOOK_URL or '(не задан — бот НЕ подключит webhook и не будет отвечать в Telegram)'}")
    logger.info(f"WEBHOOK_SECRET present: {bool(settings.WEBHOOK_SECRET)}")
    logger.info(f"WEBAPP_URL: {settings.WEBAPP_URL}")

    log_level = (settings.LOG_LEVEL or "info").lower()
    if log_level not in VALID_LOG_LEVELS:
        logger.warning(
            f"LOG_LEVEL={settings.LOG_LEVEL!r} — недопустимое значение (похоже, переменные окружения "
            f"перепутаны в панели хостинга, например LOG_LEVEL содержит значение другой переменной). "
            f"Используется 'info' вместо падения приложения."
        )
        log_level = "info"

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
