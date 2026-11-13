# MEMIASMA // NEON TERMINAL

Асинхронный starter-проект Telegram Mini App: FastAPI + aiogram 3 + PostgreSQL + SQLAlchemy 2 + React/Vite.

## 1. Требования
- Python 3.11+
- Node.js 20+
- Docker Desktop / Docker Compose
- Telegram bot token от BotFather

## 2. Локальный запуск
```bash
cp .env.example .env
# Заполните BOT_TOKEN, ADMIN_ID, SECRET_KEY и MINI_APP_URL
# Для локальной разработки MINI_APP_URL должен быть HTTPS URL, доступным Telegram WebApp.
docker compose up --build
```
Frontend: http://localhost:5173  
Backend health: http://localhost:8000/api/health  
OpenAPI: http://localhost:8000/docs

Telegram Mini App требует HTTPS и запуска из Telegram. Для локальной разработки используйте HTTPS tunnel и установите его URL в MINI_APP_URL и CORS_ORIGINS.

## 3. Запуск без Docker
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```
В другом терминале:
```bash
cd frontend
npm install
npm run dev
```

## 4. База данных и миграции
В development таблицы создаются автоматически. Для production используйте Alembic migration workflow; не применяйте `create_all` при каждом старте. Конфигурация Alembic находится в корне проекта. Создание и применение первой ревизии:
```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## 5. Telegram Bot
Создайте бота через BotFather, задайте Web App URL и заполните `BOT_TOKEN`, `ADMIN_ID`, `MINI_APP_URL`. Для polling используйте отдельный процесс с `await backend.main.polling()`; для webhook задайте `TELEGRAM_WEBHOOK_URL` и `TELEGRAM_WEBHOOK_SECRET`.

## 6. xRocket
Платёжный клиент использует актуальный Pay API (`https://pay.api.testnet.xrocket.exchange` для testnet, production host — `https://pay.api.xrocket.exchange`), Bearer token и `POST /api/v1/invoices`. По умолчанию `XROCKET_LIVE_ENABLED=false`: вызовы провайдера заблокированы. Подпись webhook проверяется по актуальной схеме `HMAC_SHA256(secret, timestamp + "." + raw_body)`, заголовкам `Signature`, `Signature-Timestamp`, `Signature-Version: v1` и окну свежести 5 минут. Сверяйте контракт с официальной документацией перед развёртыванием. Не публикуйте API-ключи.

**Важно:** xRocket Pay API и Legacy API имеют разные контракты. В кабинете приложения должен быть выбран Pay API / Current. Текущий код не является сертифицированным платёжным интеграционным модулем: обязательны тесты на testnet, проверка event deduplication и reconciliation до любых реальных платежей. Покупка не должна считаться оплаченной по возврату браузера.

## 7. Production checklist
- Вынести миграции в Alembic и запускать их отдельным deployment job.
- Использовать секреты из secret manager, TLS, reverse proxy и ограниченный CORS.
- Заменить локальный rate limit на Redis-backed, FSM MemoryStorage на Redis storage, добавить durable webhook idempotency ledger и outbox для доставки.
- Добавить тесты подписи initData/webhook, повторных callback, конкурентных покупок и прав администратора.
- Реализовать подтверждённую схему xRocket и reconciliation; ручная проверка возвратов/аукциона обязательна.
- Не хранить цифровые секреты в открытом виде в БД; хранить файлы в private object storage с одноразовыми ссылками.
- Не использовать реальные пользовательские средства до юридической, платёжной и security-проверки.

## 8. Функциональные границы текущей версии
Реализованы каркас авторизации, API каталога, создание тикетов, запросы сметы, измерение HTTP latency, основные bot-команды и базовая FSM добавления товара/ответа на тикет. Аукционные ставки, автоматические возвраты, полноценная CRM-рассылка, промокоды, загрузка файлов и доставка защищённых архивов намеренно не включены в live режим: их нельзя безопасно имитировать как завершённые денежные процессы.
