#!/bin/bash
# Локальный предпросмотр Mini App на sqlite, без вебхука и Redis.
cd "$(dirname "$0")/.."
source .venv/bin/activate
export DATABASE_URL="sqlite+aiosqlite:///./preview.db"
export WEBHOOK_URL=""
export REDIS_URL=""
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
