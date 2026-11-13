import time, asyncio, uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_session
from ..models import User, PortfolioItem, Product, Order, BuilderModule, AuctionSlot, SupportTicket, TicketMessage
from ..config import settings
from ..xrocket import xrocket, XRocketError

router = APIRouter(prefix="/api")

def tg_user(request: Request): return request.state.tg_user["user"]
async def get_or_create_user(db: AsyncSession, data: dict) -> User:
    tid = int(data["id"])
    user = await db.scalar(select(User).where(User.telegram_id == tid))
    if not user:
        user = User(telegram_id=tid, username=data.get("username"), first_name=data.get("first_name"))
        db.add(user); await db.flush()
    return user

@router.get("/health")
async def health(): return {"status":"ok"}

@router.get("/init")
async def init(request: Request, db: AsyncSession=Depends(get_session)):
    data=tg_user(request); user=await get_or_create_user(db,data); await db.commit()
    return {"user":{"id":user.telegram_id,"username":user.username},"maintenance":False,"currency":settings.default_currency}

@router.get("/portfolio")
async def portfolio(db: AsyncSession=Depends(get_session)):
    rows=(await db.scalars(select(PortfolioItem).where(PortfolioItem.is_published.is_(True)).order_by(PortfolioItem.id.desc()))).all()
    return [{"id":x.id,"title":x.title,"description":x.description,"stack":x.stack,"metrics":x.metrics} for x in rows]

@router.get("/store")
async def store(db: AsyncSession=Depends(get_session)):
    rows=(await db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.id.desc()))).all()
    return [{"id":p.id,"title":p.title,"description":p.description,"category":p.category,"tags":p.tags,"version_hash":p.version_hash,"price_usd":float(p.price_usd),"currency":p.currency} for p in rows]

class BuyRequest(BaseModel): product_id:int; currency:str="USDT"; promo_code:str|None=None
@router.post("/store/buy")
async def buy(body:BuyRequest, request:Request, db:AsyncSession=Depends(get_session)):
    user=await get_or_create_user(db,tg_user(request)); product=await db.get(Product,body.product_id)
    if not product or not product.is_active: raise HTTPException(404,"Product unavailable")
    currency=body.currency.upper()
    if currency not in {"USDT","TON","NOT","GRAM"}: raise HTTPException(422,"Unsupported currency")
    if currency != product.currency.upper(): raise HTTPException(422,"This product is priced in a different settlement currency; no implicit FX conversion is applied")
    amount=Decimal(str(product.price_usd))
    # Промокоды не принимаются, пока администратор не заведёт их в отдельную таблицу.
    if body.promo_code: raise HTTPException(422,"Promo code is not configured")
    order=Order(user_id=user.id,product_id=product.id,amount=amount,currency=currency,status="pending")
    db.add(order); await db.flush()
    try:
        invoice=await xrocket.create_invoice(str(amount),currency,product.title,str(order.id))
        order.provider_invoice_id=str(invoice.get("id") or invoice.get("invoice_id")); order.invoice_url=invoice.get("link") or invoice.get("pay_url")
        if not order.provider_invoice_id or not order.invoice_url: raise XRocketError("Unexpected invoice response shape")
    except Exception as exc:
        await db.rollback(); raise HTTPException(503,str(exc))
    await db.commit(); return {"order_id":order.id,"invoice_url":order.invoice_url,"status":order.status}

@router.get("/benchmark")
async def benchmark():
    async def probe(url):
        if not url: return None
        import httpx
        start=time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=4) as client: response=await client.get(url)
            return {"ms":round((time.perf_counter()-start)*1000,1),"status":response.status_code}
        except Exception: return {"ms":None,"status":"unavailable"}
    custom,public=await asyncio.gather(probe(settings.benchmark_custom_url),probe(settings.benchmark_public_url))
    return {"custom_node":custom,"public_node":public,"measured_at":datetime.now(timezone.utc).isoformat()}

class BuilderRequest(BaseModel): module_ids:list[int]=Field(max_length=30); brief:str=Field(min_length=10,max_length=5000); contact:str=Field(min_length=2,max_length=160)
@router.post("/builder/submit")
async def builder_submit(body:BuilderRequest,request:Request,db:AsyncSession=Depends(get_session)):
    user=await get_or_create_user(db,tg_user(request)); modules=(await db.scalars(select(BuilderModule).where(BuilderModule.id.in_(body.module_ids),BuilderModule.is_active.is_(True)))).all()
    if len(modules)!=len(set(body.module_ids)): raise HTTPException(422,"Unknown module")
    ticket=SupportTicket(user_id=user.id,subject="Architecture request")
    db.add(ticket); await db.flush(); db.add(TicketMessage(ticket_id=ticket.id,sender="user",body=f"Contact: {body.contact}\nBrief: {body.brief}\nModules: {', '.join(m.name for m in modules)}")); await db.commit()
    return {"ticket_id":ticket.id,"estimated_usd":sum(float(m.price_usd) for m in modules),"estimated_hours":sum(float(m.hours) for m in modules)}

@router.get("/builder/modules")
async def builder_modules(db:AsyncSession=Depends(get_session)):
    rows=(await db.scalars(select(BuilderModule).where(BuilderModule.is_active.is_(True)).order_by(BuilderModule.id))).all()
    return [{"id":m.id,"name":m.name,"description":m.description,"price_usd":float(m.price_usd),"hours":float(m.hours)} for m in rows]

@router.get("/auction/current")
async def auction_current(db:AsyncSession=Depends(get_session)):
    slot=await db.scalar(select(AuctionSlot).where(AuctionSlot.status=="open").order_by(AuctionSlot.deadline.asc()))
    if not slot:return {"slot":None}
    return {"slot":{"id":slot.id,"title":slot.title,"description":slot.description,"current_bid":float(slot.current_bid),"currency":slot.currency,"deadline":slot.deadline.isoformat()}}

class BidRequest(BaseModel): slot_id:int; amount:Decimal=Field(gt=0)
@router.post("/auction/bid")
async def auction_bid(body:BidRequest,request:Request,db:AsyncSession=Depends(get_session)):
    # Ставка не считается принятой до подтверждения платежа; автоматические возвраты не имитируются.
    raise HTTPException(501,"Auction payment settlement is not enabled. Contact the administrator for a verified bid flow.")

class DirectRequest(BaseModel): message:str=Field(min_length=2,max_length=4000); priority:bool=False
@router.post("/direct/send")
async def direct_send(body:DirectRequest,request:Request,db:AsyncSession=Depends(get_session)):
    user=await get_or_create_user(db,tg_user(request)); ticket=SupportTicket(user_id=user.id,priority=body.priority,subject="Priority request" if body.priority else "Direct request")
    db.add(ticket); await db.flush(); db.add(TicketMessage(ticket_id=ticket.id,sender="user",body=body.message)); await db.commit()
    return {"ticket_id":ticket.id,"priority_invoice_required":body.priority,"priority_price_usd":settings.priority_price_usd if body.priority else 0}

@router.post("/xrocket/webhook")
async def xrocket_webhook(request:Request, signature:str=Header(default=""), signature_timestamp:str=Header(default=""), signature_version:str=Header(default=""), db:AsyncSession=Depends(get_session)):
    raw=await request.body()
    if not xrocket.verify_webhook(raw,signature,signature_timestamp,signature_version): raise HTTPException(401,"Invalid webhook signature")
    import json
    payload=json.loads(raw); data=payload.get("data",{}); invoice_data=data.get("invoice",{}); invoice_id=str(invoice_data.get("id") or "")
    order=await db.scalar(select(Order).where(Order.provider_invoice_id==invoice_id).with_for_update())
    if not order: raise HTTPException(404,"Order not found")
    if order.status=="paid": return {"ok":True,"duplicate":True}
    if not (data.get("event")=="invoice_status_changed" and invoice_data.get("status")=="paid") and not (data.get("event")=="payment_status_changed" and (data.get("payment") or {}).get("status")=="paid" and (data.get("payment") or {}).get("finalizedAt")): return {"ok":True,"ignored":True}
    order.status="paid"; await db.commit()
    # Доставка выполняется ботом после проверки paid; повторный webhook безопасен.
    return {"ok":True,"order_id":order.id}
