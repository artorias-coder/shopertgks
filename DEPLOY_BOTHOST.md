# Деплой на Bothost

## 1. Подготовка репозитория

Код уже на GitHub: `https://github.com/artorias-coder/shopertgks.git`

## 2. Создание бота в панели Bothost

1. Перейдите на https://bothost.ru/create-bot.php
2. Заполните форму:
   - **Название бота**: KingStore
   - **Платформа**: Telegram
   - **Библиотека**: aiogram 3.x
   - **Bot Token**: токен от @BotFather
   - **Git URL**: `https://github.com/artorias-coder/shopertgks.git`
   - **Ветка**: `main`
3. Нажмите **Создать бота**
4. Включите опцию **Использовать домен**
5. Дождитесь деплоя

## 3. Переменные окружения

В панели Bothost добавьте переменные из `.env` файла. Пример:

```
BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_IDS=17678302367
SUPERADMIN_ID=17678302367

DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kingstore
DATABASE_URL_SYNC=postgresql://postgres:postgres@db:5432/kingstore
REDIS_URL=redis://redis:6379/0

# Или для free-тарифа (без PostgreSQL/Redis):
# DATABASE_URL=sqlite+aiosqlite:///./app.db
# REDIS_URL=

GOOGLE_SHEETS_ID=ваш_id_таблицы
GOOGLE_SYNC_INTERVAL_MINUTES=5

LIVESKLAD_API_LOGIN=...
LIVESKLAD_API_PASSWORD=...
LIVESKLAD_SHOP_ID=...
LIVESKLAD_TYPE_ORDER_ID=...
LIVESKLAD_TRADEIN_TYPE_ORDER_ID=...
LIVESKLAD_BASE_URL=https://api.livesklad.com

WEBHOOK_URL=https://bot-1783487415-6114-artorias671.bothost.tech/webhook
WEBHOOK_SECRET=случайная_строка_минимум_32_символа

WEBAPP_URL=https://bot-1783487415-6114-artorias671.bothost.tech/webapp
CHANNEL_ID=-1003650098523

APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

## 4. Команда запуска

В настройках бота в Bothost укажите **стартовую команду**:

```bash
python app/bothost.py
```

Или альтернативно:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 5. Проверка

1. Откройте `https://bot-1783487415-6114-artorias671.bothost.tech/health`
   - Должен вернуть `{"status":"ok"}`
2. Откройте `https://bot-1783487415-6114-artorias671.bothost.tech/webapp`
   - Должен открыться Mini App
3. Проверьте webhook:
   ```
   https://api.telegram.org/bot<TOKEN>/getWebhookInfo
   ```
4. Отправьте боту `/start`

## 6. Публикация Mini App в канале

После деплоя отправьте боту команду `/post_channel` (бот должен быть администратором канала).

## Важно

- В `.env` в репозитории не храните реальные токены — используйте переменные окружения Bothost.
- Для free-тарифа замените PostgreSQL на SQLite и оставьте `REDIS_URL=` пустым.
- Если Mini App не открывается, проверьте логи в панели Bothost.
