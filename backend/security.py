import hashlib, hmac, json, time
from urllib.parse import parse_qsl
from fastapi import HTTPException, Request
from .config import settings

def validate_telegram_init_data(init_data: str, max_age_seconds: int = 86400) -> dict:
    """Проверяет подпись WebApp initData по алгоритму Telegram."""
    if not settings.bot_token or not init_data:
        raise HTTPException(401, "Telegram authorization required")
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "Missing Telegram hash")
    auth_date = int(data.get("auth_date", "0"))
    if auth_date <= 0 or time.time() - auth_date > max_age_seconds or auth_date > time.time() + 60:
        raise HTTPException(401, "Expired Telegram authorization")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(401, "Invalid Telegram signature")
    try: return {**data, "user": json.loads(data.get("user", "{}"))}
    except json.JSONDecodeError: raise HTTPException(401, "Invalid Telegram user payload")

async def telegram_user(request: Request) -> dict:
    raw = request.headers.get("X-Telegram-Init-Data", "")
    return validate_telegram_init_data(raw)
