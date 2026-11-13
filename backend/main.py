import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from .config import settings
from .database import engine, Base
from .middlewares import RequestLoggingMiddleware, InitDataMiddleware, InMemoryRateLimitMiddleware
from .api.routes import router
from .handlers.user import router as user_router
from .handlers.admin import router as admin_router

logging.basicConfig(level=logging.INFO)
bot=Bot(settings.bot_token) if settings.bot_token else None
dp=Dispatcher(storage=MemoryStorage())
dp.include_router(admin_router); dp.include_router(user_router)

@asynccontextmanager
async def lifespan(app:FastAPI):
    # Для локального старта; в production миграции выполняются отдельной release-командой Alembic.
    if settings.app_env=="development":
        async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    if bot and settings.telegram_webhook_url:
        await bot.set_webhook(settings.telegram_webhook_url,secret_token=settings.telegram_webhook_secret)
    yield
    if bot: await bot.session.close()
    await engine.dispose()

app=FastAPI(title="MEMIASMA NEON TERMINAL",version="1.0.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_list,allow_credentials=True,allow_methods=["GET","POST"],allow_headers=["*"])
app.add_middleware(RequestLoggingMiddleware); app.add_middleware(InMemoryRateLimitMiddleware,limit=settings.rate_limit_per_minute); app.add_middleware(InitDataMiddleware)
app.include_router(router)

@app.post("/telegram/webhook")
async def telegram_webhook(update:dict, x_telegram_bot_api_secret_token:str|None=None):
    from fastapi import HTTPException
    if not bot: raise HTTPException(503,"Bot is not configured")
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token!=settings.telegram_webhook_secret: raise HTTPException(401,"Invalid webhook secret")
    await dp.feed_update(bot,Update.model_validate(update)); return {"ok":True}

async def polling():
    if not bot: raise RuntimeError("BOT_TOKEN is required for polling")
    await dp.start_polling(bot)

if __name__=="__main__":
    import uvicorn
    uvicorn.run("backend.main:app",host="0.0.0.0",port=8000,reload=settings.app_env=="development")
