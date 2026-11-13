from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select
from ..database import SessionLocal
from ..models import User, Order, Product
from ..config import settings

router=Router(name="user")

@router.message(CommandStart())
async def start(message:Message):
    async with SessionLocal() as db:
        user=await db.scalar(select(User).where(User.telegram_id==message.from_user.id))
        if not user:
            db.add(User(telegram_id=message.from_user.id,username=message.from_user.username,first_name=message.from_user.first_name)); await db.commit()
    keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="OPEN NEON TERMINAL",web_app=WebAppInfo(url=settings.mini_app_url))]])
    await message.answer("<b>MEMIASMA // SECURE CHANNEL</b>\nSystem online. Open the Mini App to explore the portfolio, store and contact desk.",reply_markup=keyboard)

@router.message(F.text)
async def incoming_text(message:Message):
    if message.text.startswith("/"): return
    async with SessionLocal() as db:
        user=await db.scalar(select(User).where(User.telegram_id==message.from_user.id))
        if not user:
            user=User(telegram_id=message.from_user.id,username=message.from_user.username,first_name=message.from_user.first_name); db.add(user); await db.flush()
        from ..models import SupportTicket,TicketMessage
        ticket=SupportTicket(user_id=user.id,subject="Bot message"); db.add(ticket); await db.flush()
        db.add(TicketMessage(ticket_id=ticket.id,sender="user",body=message.text)); await db.commit()
    if settings.admin_id: await message.bot.send_message(settings.admin_id,f"New message from @{message.from_user.username or message.from_user.id}:\n{message.text[:3000]}")
