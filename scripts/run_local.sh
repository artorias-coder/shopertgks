#!/bin/bash
# Запуск сервера, туннеля и бота локально для теста Mini App
# Требуется: .venv, cloudflared (brew install cloudflared)

set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "Остановка старых процессов..."
pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
pkill -9 -f "cloudflared tunnel" 2>/dev/null || true
pkill -9 -f "python app/run_bot.py" 2>/dev/null || true
sleep 2

echo "Запуск FastAPI сервера..."
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 3

echo "Запуск cloudflared туннеля..."
nohup cloudflared tunnel --url http://localhost:8000 --protocol http2 > /tmp/cf.log 2>&1 &
sleep 8

URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf.log | head -1)
if [ -z "$URL" ]; then
    echo "Не удалось получить URL туннеля. Смотрите /tmp/cf.log"
    cat /tmp/cf.log | tail -20
    exit 1
fi

echo "Mini App URL: $URL/webapp"
sed -i '' "s|WEBAPP_URL=.*|WEBAPP_URL=$URL/webapp|" .env

echo "Запуск Telegram бота..."
nohup python app/run_bot.py > /tmp/bot.log 2>&1 &
sleep 3

echo ""
echo "Готово. Открывайте: $URL/webapp"
echo "Команда для публикации в канале (бот должен быть админом): /post_channel"
