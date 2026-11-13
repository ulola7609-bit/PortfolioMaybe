import logging, time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import HTTPException
from .security import validate_telegram_init_data
from .config import settings

logger = logging.getLogger("neon.api")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        logger.info("%s %s -> %s %.1fms", request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
        return response

class InitDataMiddleware(BaseHTTPMiddleware):
    """Все /api/* кроме health и webhook требуют валидный initData."""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in ("/api/health", "/api/xrocket/webhook"):
            raw = request.headers.get("X-Telegram-Init-Data", "")
            try: request.state.tg_user = validate_telegram_init_data(raw)
            except HTTPException as exc:
                from starlette.responses import JSONResponse
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return await call_next(request)

class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Локальный лимитер для dev/одного процесса; для нескольких workers нужен Redis."""
    def __init__(self, app, limit: int = 60):
        super().__init__(app); self.limit=limit; self.hits={}
    async def dispatch(self, request: Request, call_next):
        import time
        if request.url.path.startswith("/api/") and request.url.path not in ("/api/health", "/api/xrocket/webhook"):
            key=request.headers.get("X-Telegram-Init-Data", "")[:96] or (request.client.host if request.client else "unknown")
            now=int(time.time()); window=now//60; bucket=self.hits.get((key,window),0)
            if bucket>=self.limit:
                from starlette.responses import JSONResponse
                return JSONResponse({"detail":"Rate limit exceeded"},status_code=429,headers={"Retry-After":str(60-now%60)})
            self.hits[(key,window)]=bucket+1
            if len(self.hits)>10000:self.hits={k:v for k,v in self.hits.items() if k[1]>=window-1}
        return await call_next(request)
