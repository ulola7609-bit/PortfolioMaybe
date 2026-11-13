from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from ..config import settings
from ..database import SessionLocal
from ..models import Product, User, Order, PortfolioItem, AuctionSlot, SupportTicket, TicketMessage

router=Router(name="admin")
def is_admin(user_id:int)->bool: return bool(settings.admin_id and user_id==settings.admin_id)
class ProductFlow(StatesGroup): title=State(); description=State(); price=State(); category=State()
class ReplyFlow(StatesGroup): ticket_id=State(); body=State()

@router.message(Command("admin"))
async def admin_home(message:Message):
    if not is_admin(message.from_user.id): return await message.answer("Access denied")
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Add product",callback_data="adm:add")],[InlineKeyboardButton(text="Analytics",callback_data="adm:stats")],[InlineKeyboardButton(text="Open tickets",callback_data="adm:tickets")]])
    await message.answer("<b>NEON CONTROL // ADMIN</b>\nSelect operation:",reply_markup=kb)

@router.callback_query(F.data=="adm:add")
async def add_product_start(call:CallbackQuery,state:FSMContext):
    if not is_admin(call.from_user.id): return await call.answer("Denied",show_alert=True)
    await state.set_state(ProductFlow.title); await call.message.answer("Product title?"); await call.answer()

@router.message(ProductFlow.title)
async def product_title(message:Message,state:FSMContext):
    await state.update_data(title=message.text[:160]); await state.set_state(ProductFlow.description); await message.answer("Description?")
@router.message(ProductFlow.description)
async def product_description(message:Message,state:FSMContext):
    await state.update_data(description=message.text[:3000]); await state.set_state(ProductFlow.price); await message.answer("Price in USD (number)?")
@router.message(ProductFlow.price)
async def product_price(message:Message,state:FSMContext):
    try: price=float(message.text); assert 0<=price<=100000
    except Exception:return await message.answer("Enter a valid price between 0 and 100000.")
    await state.update_data(price=price); await state.set_state(ProductFlow.category); await message.answer("Category: Bots / Web3-RPC / Parsers / Mini Apps")
@router.message(ProductFlow.category)
async def product_category(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id): await state.clear(); return
    data=await state.get_data(); category=message.text[:40]
    async with SessionLocal() as db:
        db.add(Product(title=data['title'],description=data['description'],price_usd=data['price'],category=category,currency="USDT",delivery_type="text",delivery_payload="Contact admin for fulfilment")); await db.commit()
    await state.clear(); await message.answer("Product created. Add delivery material through a secured deployment workflow.")

@router.callback_query(F.data=="adm:stats")
async def stats(call:CallbackQuery):
    if not is_admin(call.from_user.id):return await call.answer("Denied",show_alert=True)
    async with SessionLocal() as db:
        users=await db.scalar(select(func.count(User.id))) or 0
        orders=await db.scalar(select(func.count(Order.id))) or 0
        revenue=await db.scalar(select(func.coalesce(func.sum(Order.amount),0)).where(Order.status=="paid")) or 0
    await call.message.answer(f"Users: {users}\nOrders: {orders}\nRecorded paid volume: {revenue}"); await call.answer()

@router.callback_query(F.data=="adm:tickets")
async def tickets(call:CallbackQuery):
    if not is_admin(call.from_user.id):return await call.answer("Denied",show_alert=True)
    async with SessionLocal() as db:
        rows=(await db.scalars(select(SupportTicket).where(SupportTicket.status=="open").order_by(SupportTicket.priority.desc(),SupportTicket.created_at.asc()).limit(10))).all()
    if not rows: await call.message.answer("No open tickets.")
    for t in rows:
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Reply",callback_data=f"adm:reply:{t.id}")]])
        await call.message.answer(f"Ticket #{t.id} {'[PRIORITY]' if t.priority else ''} — {t.subject}",reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm:reply:"))
async def reply_start(call:CallbackQuery,state:FSMContext):
    if not is_admin(call.from_user.id):return await call.answer("Denied",show_alert=True)
    ticket_id=int(call.data.split(":")[-1]); await state.update_data(ticket_id=ticket_id); await state.set_state(ReplyFlow.body)
    await call.message.answer(f"Send reply for ticket #{ticket_id}:"); await call.answer()

@router.message(ReplyFlow.body)
async def reply_send(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id):await state.clear();return
    data=await state.get_data(); ticket_id=data['ticket_id']
    async with SessionLocal() as db:
        ticket=await db.get(SupportTicket,ticket_id); user=await db.get(User,ticket.user_id) if ticket else None
        if not ticket or not user: await message.answer("Ticket not found."); await state.clear(); return
        db.add(TicketMessage(ticket_id=ticket_id,sender="admin",body=message.text)); await db.commit(); telegram_id=user.telegram_id
    await message.bot.send_message(telegram_id,f"<b>@memiasma // SUPPORT</b>\n{message.text}")
    await message.answer("Reply delivered."); await state.clear()
