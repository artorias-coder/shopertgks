# KingStore Telegram Bot

MVP Telegram-бота для магазина Apple-техники в формате `@kingstoreloyalty_bot`: каталог, заявки на товар, Trade-in, розыгрыши, поиск, интеграция с Google Таблицами и CRM LiveSklad.

## Технический стек

- Python 3.12
- aiogram 3 (Telegram Bot)
- FastAPI + uvicorn (API)
- SQLAlchemy + PostgreSQL
- Redis + Celery (очереди и фоновые задачи)
- gspread (Google Sheets)
- httpx (LiveSklad REST API)
- Docker + Docker Compose

## Структура проекта

```
app/
  bot/          # aiogram handlers (client, catalog, cart, order, tradein, giveaways, admin, support)
  services/     # Google Sheets, LiveSklad, notifications
  api/          # FastAPI endpoints
  config.py     # настройки из .env
  database.py   # подключение к БД
  models.py     # SQLAlchemy модели
  main.py       # FastAPI приложение
  run_bot.py    # точка входа бота
  tasks.py      # Celery задачи
docker-compose.yml
Dockerfile
requirements.txt
.env.example
```

## Запуск

1. Скопируйте `.env.example` в `.env` и заполните переменные:
   - `BOT_TOKEN` — токен от BotFather
   - `ADMIN_IDS` и `SUPERADMIN_ID`
   - `GOOGLE_SHEETS_ID` и путь к `GOOGLE_CREDENTIALS_JSON`
   - `LIVESKLAD_API_TOKEN`, `LIVESKLAD_SHOP_ID`

2. Запустите инфраструктуру:
   ```bash
   docker compose up -d db redis
   ```

3. Создайте таблицы:
   ```bash
   python -c "import asyncio; from app.main import startup; asyncio.run(startup())"
   ```

4. Запустите бота, API и воркер:
   ```bash
   docker compose up -d api bot worker
   ```

## Использование

- **Каталог** — категории товаров (iPhone, iPad, Apple Watch, AirPods, Samsung), поиск, карточка товара с характеристиками, кнопка «Заказать».
- **Заявка на товар** — при нажатии «Заказать» клиент вводит имя и телефон, заявка уходит менеджеру и в LiveSklad.
- **Trade-in** — клиент выбирает тип устройства, модель, состояние батареи и корпуса, получает оценку и отправляет заявку.
- **Розыгрыши** — участие в активных розыгрышах, приглашение друзей, просмотр результатов.
- **Узнать лучшую цену / Написать менеджеру** — быстрая заявка с вопросом.
- **Корзина** — классическая корзина с оформлением заказа (как запасной вариант).
- **Администраторы** получают меню с заявками, Trade-in, розыгрышами, синхронизацией, статистикой и рассылками.
- **Синхронизация Google Sheets** выполняется автоматически и вручную.
- **Заявки отправляются в LiveSklad**; при ошибке получают статус `pending_sync` и повторяются через Celery.

## Для старта нужно получить

1. Telegram-токен бота.
2. Google Таблица с товарами (колонки: sku, name, category, subcategory, description, price, old_price, discount, stock, photo_url, status, livesklad_id).
3. API-токен LiveSklad и ID магазина.
4. Список Telegram ID администраторов.
5. Логотип, условия доставки и оплаты.
6. 5–10 примеров товаров.

## Примечание

Формат и UX реализованы по аналогии с ботом @kingstoreloyalty_bot (ссылка предоставлена заказчиком). Тонкие детали интерфейса будут уточнены после предоставления тестовых данных и доступа к API.
